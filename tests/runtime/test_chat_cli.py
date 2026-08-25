from __future__ import annotations

import asyncio
from argparse import Namespace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ontchatbot.cli import chat
from ontchatbot.cli.chat import _parse_args


def test_chat_cli_does_not_accept_a_provider_selection() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--model-dir", "generator", "--device", "cuda"])


def test_interactive_chat_session_uses_one_event_loop(monkeypatch) -> None:
    import agents

    loop_ids = []

    async def fake_runner(agent, question):
        loop_ids.append(id(asyncio.get_running_loop()))
        return SimpleNamespace(final_output=question)

    questions = iter(("câu một", "câu hai", ""))
    monkeypatch.setattr(chat, "_parse_args", lambda: Namespace(
        llm="mô-hình", model_dir=Path("generator"), base_url=None, hoi=None
    ))
    monkeypatch.setattr(chat.OnnxClassifierGenerator, "load", lambda _: "generator")
    monkeypatch.setattr(chat, "OntologyChatbot", lambda _: "chatbot")
    monkeypatch.setattr(chat, "build_agent", lambda *args, **kwargs: "agent")
    monkeypatch.setattr(agents.Runner, "run", fake_runner)
    monkeypatch.setattr("builtins.input", lambda _: next(questions))

    chat.main()

    assert len(loop_ids) == 2
    assert len(set(loop_ids)) == 1


def test_interactive_chat_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys) -> None:
    monkeypatch.setattr(chat, "_parse_args", lambda: Namespace(
        llm="mô-hình", model_dir=Path("generator"), base_url=None, hoi=None
    ))
    monkeypatch.setattr(chat.OnnxClassifierGenerator, "load", lambda _: "generator")
    monkeypatch.setattr(chat, "OntologyChatbot", lambda _: "chatbot")
    monkeypatch.setattr(chat, "build_agent", lambda *args, **kwargs: "agent")

    def interrupted_input(_):
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupted_input)

    chat.main()

    assert "Gõ câu hỏi rồi Enter" in capsys.readouterr().out


def test_interactive_trace_supports_the_agent_tool_lookup_protocol(monkeypatch, capsys) -> None:
    """The interactive wrapper must expose every stage used by the cached tool."""

    from agents.tool_context import ToolContext
    from ontchatbot.runtime import agent as agent_runtime
    from ontchatbot.runtime.lookup_pool import AsyncLookupPool
    from ontchatbot.runtime.pipeline import Classification, PreparedKeyword, QueryResolution

    class FakeChatbot:
        def __init__(self) -> None:
            self.prepared = []
            self.classified = []
            self.executed = []

        def prepare_keywords(self, keywords):
            self.prepared.append(list(keywords))
            return tuple(PreparedKeyword(keyword, keyword) for keyword in keywords)

        def classify_many(self, model_inputs):
            self.classified.append(list(model_inputs))
            return tuple(Classification("test", "SELECT * WHERE {}") for _ in model_inputs)

        def execute_query(self, query, *, max_rows):
            self.executed.append((query, max_rows))
            return QueryResolution("ok", ())

        def render_many(self, prepared, choices, resolutions):
            return json.dumps({"keywords": [item.original for item in prepared]})

    class CapturingPool(AsyncLookupPool):
        instances = []

        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self.instances.append(self)

    monkeypatch.setattr(agent_runtime, "AsyncLookupPool", CapturingPool)
    chatbot = FakeChatbot()
    agent = agent_runtime.build_agent(
        chat._Trace(chatbot),
        model="test-model",
        api_key="test-key",
        lookup_workers=1,
    )
    tool = agent.tools[0]
    arguments = '{"tu_khoa":["học phí"]}'

    async def exercise():
        try:
            return await tool.on_invoke_tool(
                ToolContext(
                    None,
                    tool_name=tool.name,
                    tool_call_id="lookup",
                    tool_arguments=arguments,
                ),
                arguments,
            )
        finally:
            await CapturingPool.instances[0].aclose()

    assert json.loads(asyncio.run(exercise())) == {"keywords": ["học phí"]}
    assert chatbot.prepared == [["học phí"]]
    assert chatbot.classified == [["học phí"]]
    assert chatbot.executed == [("SELECT * WHERE {}", 100)]
    assert "tra ['học phí']" in capsys.readouterr().out
