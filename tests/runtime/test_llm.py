from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ontchatbot.runtime.llm import (
    MAX_RETRIES,
    ChatDelta,
    Endpoint,
    FallbackClient,
    GeminiClient,
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


# --- chuyển sang mô hình dự phòng ------------------------------------------------------

_XONG = ('data: {"choices":[{"index":0,"delta":{"content":"%s"},"finish_reason":null}]}\n\n'
         'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')


def _diem_cuoi(*models: str) -> list[Endpoint]:
    return [Endpoint(f"https://{ten.split('/')[0]}.test/v1/", "khoa", ten) for ten in models]


def _chuoi(cach_tra_loi, **them):
    """Chuỗi dự phòng mà mỗi điểm cuối trả lời theo ``cach_tra_loi[tên mô hình]``."""

    goi: list[str] = []

    def mo(endpoint: Endpoint) -> httpx.AsyncClient:
        def respond(request: httpx.Request) -> httpx.Response:
            goi.append(endpoint.model)
            return cach_tra_loi[endpoint.model](request)

        return httpx.AsyncClient(base_url=endpoint.base_url, transport=httpx.MockTransport(respond))

    return goi, FallbackClient(_diem_cuoi(*cach_tra_loi), open_client=mo, sleep=_no_wait, **them)


def _chay(client) -> list[str]:
    async def run() -> list[str]:
        return [d.content async for d in client.stream(messages=[{"role": "user", "content": "hỏi"}], tools=[])]

    return asyncio.run(run())


def test_a_silent_model_hands_the_turn_to_the_next_one() -> None:
    def im_lang(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("không trả lời")

    goi, client = _chuoi({"chinh/im": im_lang,
                          "duphong/noi": lambda _r: httpx.Response(200, content=(_XONG % "xong").encode())})

    assert "".join(_chay(client)) == "xong"
    assert goi == ["chinh/im", "duphong/noi"]


def test_the_broken_endpoint_is_skipped_on_the_next_turn() -> None:
    """Lượt sau phải đi thẳng tới nơi đang trả lời, không dò lại từ đầu."""

    def im_lang(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("không trả lời")

    goi, client = _chuoi({"chinh/im": im_lang,
                          "duphong/noi": lambda _r: httpx.Response(200, content=(_XONG % "xong").encode())},
                         clock=lambda: 0.0)

    _chay(client)
    _chay(client)

    assert goi == ["chinh/im", "duphong/noi", "duphong/noi"]


def test_a_model_that_broke_after_speaking_does_not_answer_twice() -> None:
    """Đã có chữ tới người dùng thì không được chuyển nơi khác, nếu không câu trả lời sẽ lặp."""

    dang_do = 'data: {"choices":[{"index":0,"delta":{"content":"nửa câu"},"finish_reason":null}]}\n\n'

    goi, client = _chuoi({"chinh/nua_chung": lambda _r: httpx.Response(200, content=dang_do.encode()),
                          "duphong/noi": lambda _r: httpx.Response(200, content=(_XONG % "xong").encode())})

    with pytest.raises(LightningProtocolError):
        _chay(client)
    assert goi == ["chinh/nua_chung"]


def test_a_tool_call_without_an_index_is_still_one_call() -> None:
    """Google AI Studio đánh dấu lời gọi bằng ``id`` chứ không gửi ``index``."""

    stream = (
        'data: {"choices":[{"index":0,"delta":{"tool_calls":[{"id":"call_1","type":"function",'
        '"extra_content":{"google":{"thought_signature":"chu-ky"}},'
        '"function":{"name":"lookup_academic_information","arguments":"{\\"keywords\\":[\\"học phí\\"]}"}}]},'
        '"finish_reason":null}]}\n\n'
        'data: {"choices":[{"index":0,"delta":{},"finish_reason":"tool_calls"}]}\n\n'
        "data: [DONE]\n\n"
    )

    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=stream.encode())

    async def run() -> list[ChatDelta]:
        async with httpx.AsyncClient(
            base_url="https://gemini.test/v1/", transport=httpx.MockTransport(respond)
        ) as http:
            return [
                delta
                async for delta in LightningClient(http, model="gemini", sleep=_no_wait).stream(
                    messages=[{"role": "user", "content": "học phí"}], tools=[]
                )
            ]

    deltas = asyncio.run(run())

    assert deltas[0].tool_calls == (
        ToolCallDelta(
            index=0,
            call_id="call_1",
            name="lookup_academic_information",
            arguments='{"keywords":["học phí"]}',
            # Chữ ký phải về tới agent để gửi lại nguyên vẹn, không thì Gemini 3 từ chối lượt sau.
            extra_content={"google": {"thought_signature": "chu-ky"}},
        ),
    )


def test_two_calls_without_an_index_stay_apart() -> None:
    """Hai lời gọi trong cùng một luồng không được nhập làm một."""

    stream = (
        'data: {"choices":[{"delta":{"tool_calls":[{"id":"call_1","function":{"name":"lookup","arguments":"{}"}},'
        '{"id":"call_2","function":{"name":"lookup","arguments":"{}"}}]},"finish_reason":null}]}\n\n'
        "data: [DONE]\n\n"
    )

    def respond(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, content=stream.encode())

    async def run() -> list[ChatDelta]:
        async with httpx.AsyncClient(
            base_url="https://gemini.test/v1/", transport=httpx.MockTransport(respond)
        ) as http:
            return [
                delta
                async for delta in LightningClient(http, model="gemini", sleep=_no_wait).stream(
                    messages=[], tools=[]
                )
            ]

    (delta,) = asyncio.run(run())

    assert [call.index for call in delta.tool_calls] == [0, 1]


def test_another_provider_is_told_the_lookup_in_words() -> None:
    """Lời gọi công cụ mang chữ ký của nơi sinh ra nó, nhà khác nhận lại sẽ từ chối."""

    thay: list[list[dict]] = []

    def im_lang(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("không trả lời")

    def noi(request: httpx.Request) -> httpx.Response:
        thay.append(json.loads(request.content)["messages"])
        return httpx.Response(200, content=(_XONG % "xong").encode())

    goi, client = _chuoi({"chinh/im": im_lang, "duphong/noi": noi})
    hoi_thoai = [
        {"role": "user", "content": "học phí"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function"}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "status=ok; nộp qua VNPAY"},
    ]

    async def run() -> None:
        async for _ in client.stream(messages=hoi_thoai, tools=[]):
            pass

    asyncio.run(run())

    assert goi == ["chinh/im", "duphong/noi"]
    assert thay == [[
        {"role": "user", "content": "học phí"},
        {"role": "user", "content": "Kết quả tra cứu:\nstatus=ok; nộp qua VNPAY"},
    ]]


def _cham(giay: float, than: bytes):
    """Điểm cuối trả lời sau ``giay``, để thử hạn chờ mảnh đầu."""

    async def respond(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(giay)
        return httpx.Response(200, content=than)

    return respond


def test_a_slow_first_chunk_moves_on_while_nobody_is_reading() -> None:
    """Chưa có chữ nào tới người đọc thì đổi nơi trả lời còn kịp, không ai thấy gì."""

    goi, client = _chuoi({"chinh/cham": _cham(0.2, (_XONG % "muộn").encode()),
                          "duphong/nhanh": lambda _r: httpx.Response(200, content=(_XONG % "xong").encode())},
                         first_chunk=0.02)

    assert "".join(_chay(client)) == "xong"
    assert goi == ["chinh/cham", "duphong/nhanh"]


def test_the_last_endpoint_is_given_all_the_time_it_needs() -> None:
    """Không còn nơi nào khác thì chờ thêm vẫn hơn là bỏ lượt."""

    goi, client = _chuoi({"chinh/im": lambda _r: (_ for _ in ()).throw(httpx.ReadTimeout("không trả lời")),
                          "duphong/cham": _cham(0.2, (_XONG % "muộn nhưng có").encode())},
                         first_chunk=0.02)

    assert "".join(_chay(client)) == "muộn nhưng có"
    assert goi == ["chinh/im", "duphong/cham"]


def test_the_spare_provider_is_given_its_own_extra_instructions() -> None:
    """Lời nhắc chung phải giữ nguyên chữ, nên dặn riêng một nhà thì dặn ở lớp của nhà đó."""

    seen: list[list[dict]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content)["messages"])
        return httpx.Response(200, content=(_XONG % "xong").encode())

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="https://gemini.test/v1/", transport=httpx.MockTransport(respond)
        ) as http:
            for lop in (LightningClient, GeminiClient):
                async for _ in lop(http, model="m", sleep=_no_wait).stream(
                    messages=[{"role": "system", "content": "lời nhắc chung"},
                              {"role": "user", "content": "hỏi"}],
                    tools=[],
                ):
                    pass

    asyncio.run(run())

    assert seen[0][0]["content"] == "lời nhắc chung"
    assert seen[1][0]["content"].startswith("lời nhắc chung\n\n")
    assert "Mỗi nguồn chỉ nhắc MỘT lần" in seen[1][0]["content"]
    # Câu hỏi của người dùng không bị đụng vào.
    assert seen[1][1] == {"role": "user", "content": "hỏi"}
