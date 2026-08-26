from __future__ import annotations

import asyncio
from argparse import Namespace
from pathlib import Path

import pytest

from ontchatbot.cli import chat
from ontchatbot.cli.chat import _parse_args, _runtime_args
from ontchatbot.runtime.agent import AgentEvent


def _args(*, question=None) -> Namespace:
    return Namespace(
        llm="mô-hình", model_dir=Path("generator"), base_url=None, hoi=question
    )


def test_chat_cli_does_not_accept_a_provider_selection() -> None:
    with pytest.raises(SystemExit):
        _parse_args(["--model-dir", "generator", "--device", "cuda"])


def test_runtime_args_honors_the_llm_base_url_environment(monkeypatch) -> None:
    monkeypatch.setenv("ONTCHATBOT_LLM_BASE_URL", "https://llm.example/api/v1/")

    assert _runtime_args(_args()).base_url == "https://llm.example/api/v1/"


def test_interactive_chat_session_uses_one_event_loop(monkeypatch) -> None:
    loop_ids = []

    class Agent:
        async def stream(self, messages):
            loop_ids.append(id(asyncio.get_running_loop()))
            yield AgentEvent("completed", content=messages[-1]["content"])

    questions = iter(("câu một", "câu hai", ""))
    monkeypatch.setattr(chat, "_parse_args", lambda: _args())
    monkeypatch.setattr(chat, "_build_agent", lambda _args: Agent())
    monkeypatch.setattr("builtins.input", lambda _: next(questions))

    chat.main()

    assert len(loop_ids) == 2
    assert len(set(loop_ids)) == 1


def test_interactive_chat_exits_cleanly_on_keyboard_interrupt(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(chat, "_parse_args", lambda: _args())
    monkeypatch.setattr(chat, "_build_agent", lambda _args: object())
    monkeypatch.setattr(
        "builtins.input", lambda _: (_ for _ in ()).throw(KeyboardInterrupt())
    )

    chat.main()

    assert "Gõ câu hỏi rồi Enter" in capsys.readouterr().out


def test_cli_shows_the_lookup_keywords_from_the_shared_agent_loop(
    monkeypatch, capsys
) -> None:
    class Agent:
        async def stream(self, _messages):
            yield AgentEvent("lookup_started", keywords=("học phí",))
            yield AgentEvent("text_delta", content="Kết quả")
            yield AgentEvent("completed", content="Kết quả")

    monkeypatch.setattr(chat, "_parse_args", lambda: _args(question="học phí"))
    monkeypatch.setattr(chat, "_build_agent", lambda _args: Agent())

    chat.main()

    output = capsys.readouterr().out
    assert "tra ['học phí']" in output
    assert "Kết quả" in output
