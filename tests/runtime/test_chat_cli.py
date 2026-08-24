from __future__ import annotations

import asyncio
from argparse import Namespace
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
