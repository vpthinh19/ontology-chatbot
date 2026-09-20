"""Gọi mô hình qua giao thức chat-completions (tương thích OpenAI) và đọc câu trả lời chảy dần (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

#: Số lần gọi lại sau lần đầu khi dịch vụ mô hình trục trặc tạm thời.
MAX_RETRIES = 3
#: Phải chờ lâu hơn chừng này thì báo người dùng thử lại sau, thay vì để màn hình đứng im.
MAX_RETRY_WAIT_SECONDS = 10.0
_RETRYABLE_STATUS = {408, 409, 429}
#: Dịch vụ quá tải chứ không hỏng.
_BUSY_STATUS = {429, 503}


class LightningProtocolError(RuntimeError):
    """Luồng trả về không đúng giao thức SSE (thiếu ``[DONE]``)."""


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
    """Gửi hội thoại kèm khai báo công cụ, trả về từng mảnh ``ChatDelta``.

    Lỗi tạm thời (mạng, 408/409/429, 5xx) được gọi lại tối đa ``MAX_RETRIES`` lần, nhưng chỉ khi chưa
    có chữ nào tới người dùng.
    """

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        model: str,
        retries: int = MAX_RETRIES,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._http = http
        self._model = model
        self._retries = retries
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
        for retry in range(self._retries + 1):
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
                if retry == self._retries or wait > MAX_RETRY_WAIT_SECONDS:
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


#: Chờ mảnh đầu tiên của một điểm cuối lâu hơn chừng này thì chuyển sang điểm cuối sau.
#: Các mô hình lành lặn trả mảnh đầu trong khoảng một giây rưỡi.
ENDPOINT_READ_TIMEOUT_SECONDS = 12.0
#: Điểm cuối vừa hỏng bị bỏ qua trong chừng này, để lượt sau không phải dò lại từ đầu.
ENDPOINT_COOLDOWN_SECONDS = 120.0


@dataclass(frozen=True)
class Endpoint:
    """Một nơi có thể trả lời: địa chỉ giao thức chat-completions, khoá và tên mô hình."""

    base_url: str
    api_key: str
    model: str

    @property
    def label(self) -> str:
        return f"{self.model} @ {self.base_url.split('//', 1)[-1].split('/', 1)[0]}"


class FallbackClient:
    """Gọi lần lượt các điểm cuối cho tới khi có mảnh trả lời đầu tiên.

    Điểm cuối hỏng bị ghi nhớ trong ``cooldown`` giây nên chỉ lượt đầu phải dò; các lượt sau đi thẳng
    tới nơi đang trả lời. Đã có chữ tới người dùng thì KHÔNG đổi điểm cuối nữa, vì câu trả lời sẽ lặp.
    Mỗi điểm cuối chỉ được gọi lại khi nó là điểm cuối cuối cùng: còn nơi khác để thử thì chuyển luôn.
    """

    def __init__(
        self,
        endpoints: Sequence[Endpoint],
        *,
        open_client: Callable[[Endpoint], httpx.AsyncClient],
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
        clock: Callable[[], float] = time.monotonic,
        cooldown: float = ENDPOINT_COOLDOWN_SECONDS,
    ) -> None:
        if not endpoints:
            raise ValueError("cần ít nhất một điểm cuối mô hình")
        self._endpoints = tuple(endpoints)
        self._open_client = open_client
        self._sleep = sleep
        self._jitter = jitter
        self._clock = clock
        self._cooldown = cooldown
        self._down: dict[str, float] = {}
        self._clients: dict[str, tuple[httpx.AsyncClient, LightningClient]] = {}

    def _client(self, endpoint: Endpoint, *, last: bool) -> LightningClient:
        """Mở kết nối cho điểm cuối khi lần đầu cần tới, rồi dùng lại."""

        cached = self._clients.get(endpoint.label)
        if cached is None:
            http = self._open_client(endpoint)
            cached = (http, LightningClient(http, model=endpoint.model, retries=MAX_RETRIES if last else 0,
                                            sleep=self._sleep, jitter=self._jitter))
            self._clients[endpoint.label] = cached
        return cached[1]

    def _order(self) -> list[Endpoint]:
        """Điểm cuối chưa bị đánh dấu hỏng trước, rồi tới những cái đang trong thời gian nghỉ."""

        now = self._clock()
        sang = [e for e in self._endpoints if self._down.get(e.label, 0.0) <= now]
        return sang or list(self._endpoints)

    async def stream(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
    ) -> AsyncIterator[ChatDelta]:
        thu = self._order()
        for vi_tri, endpoint in enumerate(thu):
            emitted = False
            try:
                async for delta in self._client(endpoint, last=vi_tri == len(thu) - 1).stream(
                    messages=messages, tools=tools
                ):
                    if not emitted:
                        emitted = True
                        self._down.pop(endpoint.label, None)
                        if vi_tri:
                            logger.warning("model fallback: trả lời bằng %s", endpoint.label)
                    yield delta
                return
            except (httpx.TransportError, httpx.HTTPStatusError, LightningProtocolError, LightningBusyError) as exc:
                if emitted or vi_tri == len(thu) - 1:
                    raise
                self._down[endpoint.label] = self._clock() + self._cooldown
                logger.warning("model endpoint %s hỏng (%s: %s), chuyển sang %s",
                               endpoint.label, type(exc).__name__, str(exc)[:120], thu[vi_tri + 1].label)

    async def aclose(self) -> None:
        for http, _ in self._clients.values():
            await http.aclose()
        self._clients.clear()
