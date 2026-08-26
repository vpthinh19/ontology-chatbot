from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ontchatbot.runtime.llm import (
    ChatDelta,
    LightningClient,
    LightningProtocolError,
    ToolCallDelta,
)


def test_stream_reconstructs_the_lightning_tool_call_protocol() -> None:
    """Dropping a streamed argument fragment would make valid tool JSON invalid."""

    stream = """data: {"choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n
data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call-1","type":"function","function":{"name":"lookup_academic_information","arguments":"{\\\"key"}}]},"finish_reason":null}]}\n\n
data: {"choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"type":"","function":{"arguments":"words\\\":[\\\"học phí\\\"]}"}}]},"finish_reason":null}]}\n\n
data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\n\n
data: [DONE]\n\n"""

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/chat/completions"
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=stream.encode(),
        )

    async def run() -> list[ChatDelta]:
        async with httpx.AsyncClient(
            base_url="https://lightning.test/api/v1/",
            transport=httpx.MockTransport(respond),
        ) as http:
            client = LightningClient(http, model="gemma")
            return [
                delta
                async for delta in client.stream(
                    messages=[{"role": "user", "content": "học phí"}],
                    tools=[{"type": "function", "function": {"name": "lookup"}}],
                )
            ]

    deltas = asyncio.run(run())

    assert deltas == [
        ChatDelta(
            tool_calls=(
                ToolCallDelta(
                    index=0,
                    call_id="call-1",
                    name="lookup_academic_information",
                    arguments='{"key',
                ),
            )
        ),
        ChatDelta(
            tool_calls=(
                ToolCallDelta(
                    index=0,
                    arguments='words":["học phí"]}',
                ),
            )
        ),
        ChatDelta(finish_reason="tool_calls"),
    ]


def test_stream_sends_the_minimal_openai_compatible_request() -> None:
    seen: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"Xin chao"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
        )

    messages = [{"role": "user", "content": "xin chào"}]
    tools = [{"type": "function", "function": {"name": "lookup"}}]

    async def run() -> list[ChatDelta]:
        async with httpx.AsyncClient(
            base_url="https://lightning.test/api/v1/",
            transport=httpx.MockTransport(respond),
        ) as http:
            return [
                item
                async for item in LightningClient(http, model="gemma").stream(
                    messages=messages, tools=tools
                )
            ]

    assert asyncio.run(run()) == [
        ChatDelta(content="Xin chao", finish_reason="stop")
    ]
    assert seen == {
        "model": "gemma",
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "stream": True,
    }


def test_stream_rejects_a_truncated_response() -> None:
    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"dang do"},"finish_reason":null}]}\n\n',
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://lightning.test/api/v1/",
            transport=httpx.MockTransport(respond),
        ) as http:
            async for _ in LightningClient(http, model="gemma").stream(
                messages=[], tools=[]
            ):
                pass

    with pytest.raises(LightningProtocolError, match="DONE"):
        asyncio.run(run())


def test_stream_retries_one_connection_failure_before_any_event() -> None:
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("temporary", request=request)
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
        )

    async def run() -> list[ChatDelta]:
        async with httpx.AsyncClient(
            base_url="https://lightning.test/api/v1/",
            transport=httpx.MockTransport(respond),
        ) as http:
            return [
                item
                async for item in LightningClient(http, model="gemma").stream(
                    messages=[], tools=[]
                )
            ]

    assert asyncio.run(run()) == [ChatDelta(content="ok", finish_reason="stop")]
    assert attempts == 2


def test_stream_retries_one_retryable_http_failure_before_any_event() -> None:
    attempts = 0

    def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n',
        )

    async def run() -> list[ChatDelta]:
        async with httpx.AsyncClient(
            base_url="https://lightning.test/api/v1/",
            transport=httpx.MockTransport(respond),
        ) as http:
            return [
                item
                async for item in LightningClient(http, model="gemma").stream(
                    messages=[], tools=[]
                )
            ]

    assert asyncio.run(run()) == [ChatDelta(content="ok", finish_reason="stop")]
    assert attempts == 2
