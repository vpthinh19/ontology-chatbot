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
        AgentEvent("lookup_finished"),
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


def test_agent_loop_closes_its_runtime_resources() -> None:
    closed = []

    async def close():
        closed.append(True)

    loop = AgentLoop(
        _ScriptedClient([]),
        lambda _keywords: None,
        instructions="x",
        close=close,
    )

    asyncio.run(loop.aclose())
    assert closed == [True]
