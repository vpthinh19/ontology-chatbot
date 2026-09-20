from __future__ import annotations

import asyncio

import pytest

from ontchatbot.runtime.agent import AgentEvent, AgentLoop, AgentProtocolError
from ontchatbot.runtime.llm import ChatDelta, ToolCallDelta


class _ScriptedClient:
    def __init__(self, responses: list[list[ChatDelta]]) -> None:
        self.responses = responses
        self.requests: list[list[dict]] = []

    async def stream(self, *, messages, tools):
        self.requests.append(list(messages))
        for delta in self.responses.pop(0):
            yield delta


def test_agent_loop_executes_a_streamed_tool_call_then_answers() -> None:
    client = _ScriptedClient(
        [
            [
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
                        ToolCallDelta(index=0, arguments='words":["học phí"]}'),
                    ),
                    finish_reason="tool_calls",
                ),
            ],
            [
                ChatDelta(content="Một tín chỉ "),
                ChatDelta(content="có mức phí...", finish_reason="stop"),
            ],
        ]
    )
    looked_up: list[list[str]] = []

    async def lookup(keywords: list[str]) -> str:
        looked_up.append(keywords)
        return '{"trang_thai":"co_du_lieu","du_lieu":["mức phí..."]}'

    async def run() -> list[AgentEvent]:
        loop = AgentLoop(client, lookup, instructions="system prompt")
        return [
            event
            async for event in loop.stream(
                [{"role": "user", "content": "Học phí bao nhiêu?"}]
            )
        ]

    events = asyncio.run(run())

    assert events == [
        AgentEvent("lookup_started", keywords=("học phí",)),
        AgentEvent("lookup_finished", content='{"trang_thai":"co_du_lieu","du_lieu":["mức phí..."]}'),
        AgentEvent("text_delta", content="Một tín chỉ "),
        AgentEvent("text_delta", content="có mức phí..."),
        AgentEvent("completed", content="Một tín chỉ có mức phí..."),
    ]
    assert looked_up == [["học phí"]]
    assert client.requests[0] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "Học phí bao nhiêu?"},
    ]
    assert client.requests[1][-2:] == [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {
                        "name": "lookup_academic_information",
                        "arguments": '{"keywords":["học phí"]}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": '{"trang_thai":"co_du_lieu","du_lieu":["mức phí..."]}',
        },
    ]


def test_agent_loop_rejects_an_unknown_tool_without_executing_it() -> None:
    client = _ScriptedClient(
        [[ChatDelta(tool_calls=(ToolCallDelta(index=0, call_id="x", name="shell", arguments="{}"),))]]
    )
    called = False

    async def lookup(_keywords):
        nonlocal called
        called = True
        return ""

    async def run() -> None:
        async for _ in AgentLoop(client, lookup, instructions="x").stream([]):
            pass

    with pytest.raises(AgentProtocolError, match="shell"):
        asyncio.run(run())
    assert not called


def _answer(chunks: list[str]) -> list[AgentEvent]:
    client = _ScriptedClient([[ChatDelta(content=chunk) for chunk in chunks]])

    async def lookup(_keywords: list[str]) -> str:
        return "{}"

    async def run() -> list[AgentEvent]:
        return [event async for event in AgentLoop(client, lookup, instructions="x").stream([])]

    return asyncio.run(run())


def test_a_mark_split_across_chunks_never_reaches_the_reader() -> None:
    events = _answer(["Dữ liệu không có hạn nộp.\n[", "[THIEU_DU", "_LIEU]", "]"])

    shown = "".join(event.content for event in events if event.kind == "text_delta")
    assert "[" not in shown and "THIEU" not in shown
    assert events[-1] == AgentEvent("completed", content="Dữ liệu không có hạn nộp.", marks=("missing",))


def test_an_out_of_scope_mark_is_reported_and_plain_brackets_pass_through() -> None:
    events = _answer(["Xem [Quy chế", "](https://ntu.edu.vn). Ngoài phạm vi.\n[[NGOAI_PHAM_VI]]"])

    assert events[-1].content == "Xem [Quy chế](https://ntu.edu.vn). Ngoài phạm vi."
    assert events[-1].marks == ("out_of_scope",)


def test_a_full_answer_has_no_marks() -> None:
    assert _answer(["Học phí nộp qua ngân hàng."])[-1].marks == ()


def test_the_tool_call_goes_back_with_the_mark_its_model_put_on_it() -> None:
    """Gemini 3 đòi lại đúng chữ ký suy nghĩ nó gửi kèm lời gọi, thiếu là từ chối cả lượt."""

    client = _ScriptedClient(
        [
            [
                ChatDelta(
                    tool_calls=(
                        ToolCallDelta(
                            index=0,
                            call_id="call-1",
                            name="lookup_academic_information",
                            arguments='{"keywords":["học phí"]}',
                            extra_content={"google": {"thought_signature": "chu-ky"}},
                        ),
                    ),
                    finish_reason="tool_calls",
                )
            ],
            [ChatDelta(content="Một tín chỉ...", finish_reason="stop")],
        ]
    )

    async def lookup(_keywords: list[str]) -> str:
        return '{"trang_thai":"co_du_lieu","du_lieu":["mức phí..."]}'

    async def run() -> None:
        loop = AgentLoop(client, lookup, instructions="system prompt")
        async for _event in loop.stream([{"role": "user", "content": "Học phí bao nhiêu?"}]):
            pass

    asyncio.run(run())

    assert client.requests[1][-2]["tool_calls"][0]["extra_content"] == {
        "google": {"thought_signature": "chu-ky"}
    }
