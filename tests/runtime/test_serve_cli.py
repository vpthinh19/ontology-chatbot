from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from ontchatbot.cli.serve import _build_agent, _configure_logging, _parse_args


def _flags(*extra: str) -> list[str]:
    return ["--model-dir", "generator", "--llm", "mo-hinh-lon", *extra]


def test_serve_loads_one_classifier_behind_the_assistant(monkeypatch) -> None:
    """Máy chủ dựng đúng một bộ chọn truy vấn và đưa nó cho trợ lý."""
    args = _parse_args(_flags("--device", "cuda"))
    loaded = []
    generator = SimpleNamespace()
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "khoa-thu")
    monkeypatch.setattr(
        "ontchatbot.cli.serve.OnnxClassifierGenerator.load",
        lambda path, **kwargs: loaded.append((path, kwargs)) or generator,
    )
    built = []
    monkeypatch.setattr(
        "ontchatbot.cli.serve.build_agent",
        lambda chatbot, **kwargs: built.append((chatbot, kwargs)) or "tro-ly",
    )

    assert _build_agent(args) == "tro-ly"
    assert loaded == [(Path("generator"), {"device": "cuda"})]
    chatbot, kwargs = built[0]
    assert chatbot.generator is generator
    assert kwargs["model"] == "mo-hinh-lon"


def test_serve_stops_when_it_cannot_reach_a_language_model(monkeypatch) -> None:
    """Thiếu một trong hai thứ thì dừng ngay lúc khởi động.

    Nếu không, máy chủ lên bình thường rồi mọi câu hỏi mới hỏng, và triệu chứng
    hiện ra ở phía người dùng chứ không phải ở nhật ký khởi động.
    """

    monkeypatch.delenv("ONTCHATBOT_LLM_API_KEY", raising=False)
    monkeypatch.delenv("ONTCHATBOT_LLM_MODEL", raising=False)

    with pytest.raises(SystemExit):
        _build_agent(_parse_args(["--model-dir", "generator"]))

    monkeypatch.setenv("ONTCHATBOT_LLM_MODEL", "mo-hinh-lon")
    with pytest.raises(SystemExit):
        _build_agent(_parse_args(["--model-dir", "generator"]))


def test_serve_log_level_defaults_to_info_and_accepts_debug() -> None:
    assert _parse_args(_flags()).log_level == "info"
    assert _parse_args(_flags("--log-level", "debug")).log_level == "debug"


def test_configure_logging_uses_requested_level_and_trace_fields(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))

    _configure_logging("warning")

    assert calls == [
        {
            "level": logging.WARNING,
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        }
    ]


def test_serve_no_longer_takes_the_flags_of_the_replaced_runtime() -> None:
    """Các cờ của bộ chạy cũ phải biến mất, không im lặng bị bỏ qua.

    Một cờ bị gỡ mà vẫn nhận vào sẽ khiến lệnh triển khai cũ chạy được nhưng
    không còn tác dụng, và không ai biết.
    """
    for flag in ("--compute-type", "--inter-threads", "--compiled-dir"):
        with pytest.raises(SystemExit):
            _parse_args(_flags(flag, "gi-do"))
