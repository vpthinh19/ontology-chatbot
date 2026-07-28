from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from ontchatbot.cli.serve import _configure_logging, _load_chatbot, _parse_args


def test_serve_requires_and_loads_one_ctranslate2_artifact(monkeypatch) -> None:
    args = _parse_args(
        [
            "--model-dir",
            "generator",
            "--device",
            "cuda",
            "--compute-type",
            "int8_float16",
        ]
    )
    loaded = []
    generator = SimpleNamespace()
    monkeypatch.setattr(
        "ontchatbot.cli.serve.CTranslate2Generator.load",
        lambda path, **kwargs: loaded.append(("generator", path, kwargs)) or generator,
    )

    chatbot = _load_chatbot(args)

    assert chatbot.generator is generator
    assert loaded == [
        (
            "generator",
            Path("generator"),
            {"device": "cuda", "compute_type": "int8_float16"},
        ),
    ]


def test_serve_log_level_defaults_to_info_and_accepts_debug() -> None:
    required = ["--model-dir", "generator"]

    assert _parse_args(required).log_level == "info"
    assert _parse_args([*required, "--log-level", "debug"]).log_level == "debug"


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
