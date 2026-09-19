"""Minimal Lightning chat-completions streaming client."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import random
from typing import Any

import httpx


#: Số lần gọi lại sau lần đầu khi dịch vụ mô hình trục trặc tạm thời.
MAX_RETRIES = 3
#: Chờ lâu hơn chừng này thì báo người dùng thử lại sau: màn hình đứng im lâu
#: trông như treo, và cả lượt còn phải vừa hạn 45 giây của máy chủ.
MAX_RETRY_WAIT_SECONDS = 10.0
_RETRYABLE_STATUS = {408, 409, 429}
#: Hai mã này nghĩa là dịch vụ quá tải chứ không phải hỏng.
_BUSY_STATUS = {429, 503}


class LightningProtocolError(RuntimeError):
    """The upstream stream did not follow the advertised SSE protocol."""


class LightningBusyError(RuntimeError):
    """Dịch vụ mô hình quá tải lâu hơn mức một người đang chat chờ được."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Lightning is rate limiting; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


def _retry_after(response: httpx.Response) -> float | None:
    """Số giây chờ trong header Retry-After: dạng số giây hoặc dạng ngày giờ HTTP."""

    value = response.headers.get("retry-after", "").strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


@dataclass(frozen=True)
class ToolCallDelta:
    index: int
    call_id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass(frozen=True)
class ChatDelta:
    content: str = ""
    tool_calls: tuple[ToolCallDelta, ...] = ()
    finish_reason: str | None = None


class LightningClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        model: str,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._http = http
        self._model = model
        self._sleep = sleep
        self._jitter = jitter

    async def stream(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> AsyncIterator[ChatDelta]:
        body = {
            "model": self._model,
            "messages": list(messages),
            "tools": list(tools),
            "tool_choice": "auto",
            "stream": True,
        }
        for retry in range(MAX_RETRIES + 1):
            emitted = False
            try:
                async for delta in self._stream_once(body):
                    emitted = True
                    yield delta
                return
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                retryable = status is None or status in _RETRYABLE_STATUS or status >= 500
                # Đã hiện chữ cho người dùng thì gọi lại sẽ làm câu trả lời lặp.
                if emitted or not retryable:
                    raise
                told = _retry_after(exc.response) if status is not None else None
                # Không được bảo chờ bao lâu thì chờ 1, 2, 4 giây, thêm một chút
                # ngẫu nhiên để nhiều lượt cùng bị chặn không gọi lại cùng lúc.
                wait = told if told is not None else 2**retry + 0.5 * self._jitter()
                if retry == MAX_RETRIES or wait > MAX_RETRY_WAIT_SECONDS:
                    if status in _BUSY_STATUS:
                        raise LightningBusyError(wait) from exc
                    raise
                await self._sleep(wait)

    async def _stream_once(
        self, body: dict[str, Any]
    ) -> AsyncIterator[ChatDelta]:
        async with self._http.stream(
            "POST", "chat/completions", json=body
        ) as response:
            response.raise_for_status()
            completed = False
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    completed = True
                    break
                payload = json.loads(data)
                choices = payload.get("choices", [])
                if not choices:
                    continue
                choice = choices[0]
                delta = choice.get("delta") or {}
                content = delta.get("content")
                if not isinstance(content, str):
                    content = ""
                tool_calls = tuple(
                    ToolCallDelta(
                        index=tool_call["index"],
                        call_id=tool_call.get("id") or "",
                        name=(tool_call.get("function") or {}).get("name") or "",
                        arguments=(tool_call.get("function") or {}).get("arguments")
                        or "",
                    )
                    for tool_call in delta.get("tool_calls") or ()
                )
                finish_reason = choice.get("finish_reason")
                if content or tool_calls or finish_reason:
                    yield ChatDelta(
                        content=content,
                        tool_calls=tool_calls,
                        finish_reason=finish_reason,
                    )
            if not completed:
                raise LightningProtocolError("Lightning stream ended without [DONE]")
