"""Minimal Lightning chat-completions streaming client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
import json
from typing import Any

import httpx


class LightningProtocolError(RuntimeError):
    """The upstream stream did not follow the advertised SSE protocol."""


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
    def __init__(self, http: httpx.AsyncClient, *, model: str) -> None:
        self._http = http
        self._model = model

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
        for attempt in range(2):
            emitted = False
            try:
                async for delta in self._stream_once(body):
                    emitted = True
                    yield delta
                return
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                retryable = isinstance(exc, httpx.TransportError) or (
                    exc.response.status_code in {408, 409, 429}
                    or exc.response.status_code >= 500
                )
                if attempt == 0 and not emitted and retryable:
                    continue
                raise

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
