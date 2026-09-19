from __future__ import annotations

import asyncio
from argparse import Namespace
from pathlib import Path

from ontchatbot.cli import chat
from ontchatbot.cli.chat import _config
from ontchatbot.runtime.agent import AgentEvent


async def _closed() -> None:
    pass


def _args(*, question=None) -> Namespace:
    return Namespace(llm="mô-hình", ontology=Path("ontology.trig"), base_url=None, hoi=question)


def test_the_cli_config_honors_the_llm_base_url_and_stays_local(monkeypatch) -> None:
    monkeypatch.setenv("ONTCHATBOT_LLM_BASE_URL", "https://llm.example/api/v1/")
    monkeypatch.setenv("ONTCHATBOT_ONTOLOGY_GCS_URI", "gs://kho/ontology.trig")
    monkeypatch.setenv("ONTCHATBOT_ADMIN_TOKEN", "quan-tri")

    config = _config(_args())

    assert config.llm_base_url == "https://llm.example/api/v1/"
    assert config.ontology == Path("ontology.trig")
    assert (config.gcs_uri, config.admin_token, config.chat_log) == ("", "", False)


def test_interactive_chat_session_uses_one_event_loop(monkeypatch) -> None:
    loop_ids = []

    class Agent:
        async def stream(self, messages):
            loop_ids.append(id(asyncio.get_running_loop()))
            yield AgentEvent("completed", content=messages[-1]["content"])

    questions = iter(("câu một", "câu hai", ""))
    monkeypatch.setattr(chat, "_parse_args", lambda: _args())
    monkeypatch.setattr(chat, "_open_agent", lambda _config: (Agent(), _closed))
    monkeypatch.setattr("builtins.input", lambda _: next(questions))

    chat.main()

    assert len(loop_ids) == 2
    assert len(set(loop_ids)) == 1


def test_interactive_chat_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys) -> None:
    monkeypatch.setattr(chat, "_parse_args", lambda: _args())
    monkeypatch.setattr(chat, "_open_agent", lambda _config: (object(), _closed))
    monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    chat.main()

    assert "Gõ câu hỏi rồi Enter" in capsys.readouterr().out


def test_cli_shows_the_lookup_keywords_from_the_shared_agent_loop(monkeypatch, capsys) -> None:
    class Agent:
        async def stream(self, _messages):
            yield AgentEvent("lookup_started", keywords=("học phí",))
            yield AgentEvent("text_delta", content="Kết quả")
            yield AgentEvent("completed", content="Kết quả")

    monkeypatch.setattr(chat, "_parse_args", lambda: _args(question="học phí"))
    monkeypatch.setattr(chat, "_open_agent", lambda _config: (Agent(), _closed))

    chat.main()

    output = capsys.readouterr().out
    assert "tra ['học phí']" in output
    assert "Kết quả" in output
