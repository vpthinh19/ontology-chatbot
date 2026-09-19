from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ontchatbot.runtime.llm import (
    MAX_RETRIES,
    ChatDelta,
    LightningBusyError,
    LightningClient,
    LightningProtocolError,
    ToolCallDelta,
)


async def _no_wait(_seconds: float) -> None:
    return None


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
            client = LightningClient(http, model="gemma", sleep=_no_wait)
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
                async for item in LightningClient(http, model="gemma", sleep=_no_wait).stream(
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
            async for _ in LightningClient(http, model="gemma", sleep=_no_wait).stream(
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
                async for item in LightningClient(http, model="gemma", sleep=_no_wait).stream(
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
                async for item in LightningClient(http, model="gemma", sleep=_no_wait).stream(
                    messages=[], tools=[]
                )
            ]

    assert asyncio.run(run()) == [ChatDelta(content="ok", finish_reason="stop")]
    assert attempts == 2


_OK = b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'


def _run_with(responses: list[httpx.Response]) -> tuple[list, list[float], int]:
    """Chạy một lượt với chuỗi phản hồi dựng sẵn; trả về kết quả, các lần chờ, số lần gọi."""

    waits: list[float] = []
    calls = 0

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    def respond(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return responses[min(calls, len(responses)) - 1]

    async def run() -> list:
        async with httpx.AsyncClient(
            base_url="https://lightning.test/api/v1/",
            transport=httpx.MockTransport(respond),
        ) as http:
            client = LightningClient(http, model="gemma", sleep=sleep, jitter=lambda: 0.0)
            return [item async for item in client.stream(messages=[], tools=[])]

    try:
        result: list = asyncio.run(run())
    except Exception as exc:
        result = [exc]
    return result, waits, calls


def _ok() -> httpx.Response:
    return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=_OK)


def test_a_rate_limit_waits_as_long_as_the_service_asks() -> None:
    result, waits, calls = _run_with([httpx.Response(429, headers={"Retry-After": "3"}), _ok()])

    assert result == [ChatDelta(content="ok", finish_reason="stop")]
    assert waits == [3.0]
    assert calls == 2


def test_without_retry_after_the_waits_double() -> None:
    result, waits, _ = _run_with([httpx.Response(429)] * 3 + [_ok()])

    assert result == [ChatDelta(content="ok", finish_reason="stop")]
    assert waits == [1.0, 2.0, 4.0]


def test_a_long_requested_wait_is_reported_at_once_instead_of_waited() -> None:
    (error,), waits, calls = _run_with([httpx.Response(429, headers={"Retry-After": "40"})])

    assert isinstance(error, LightningBusyError)
    assert error.retry_after == 40.0
    assert waits == [] and calls == 1


def test_retry_after_may_be_an_http_date() -> None:
    (error,), _, _ = _run_with(
        [httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2099 07:28:00 GMT"})]
    )

    assert isinstance(error, LightningBusyError)
    assert error.retry_after > 60


def test_a_rate_limit_that_never_lifts_ends_as_busy_after_the_last_retry() -> None:
    (error,), waits, calls = _run_with([httpx.Response(429)])

    assert isinstance(error, LightningBusyError)
    assert len(waits) == MAX_RETRIES and calls == MAX_RETRIES + 1


def test_a_rejected_key_is_not_retried() -> None:
    (error,), waits, calls = _run_with([httpx.Response(401)])

    assert isinstance(error, httpx.HTTPStatusError)
    assert waits == [] and calls == 1
