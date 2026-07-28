from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from ontchatbot.cli.serve import _configure_logging, _load_chatbot, _parse_args


def test_serve_requires_and_loads_both_ctranslate2_artifacts(monkeypatch) -> None:
    args = _parse_args(
        [
            "--model-dir",
            "generator",
            "--gate-model-dir",
            "gate",
            "--device",
            "cuda",
            "--compute-type",
            "int8_float16",
        ]
    )
    loaded = []
    generator = SimpleNamespace()
    gate = SimpleNamespace()
    monkeypatch.setattr(
        "ontchatbot.cli.serve.CTranslate2Generator.load",
        lambda path, **kwargs: loaded.append(("generator", path, kwargs)) or generator,
    )
    monkeypatch.setattr(
        "ontchatbot.cli.serve.CTranslate2DomainGate.load",
        lambda path, **kwargs: loaded.append(("gate", path, kwargs)) or gate,
    )

    chatbot = _load_chatbot(args)

    assert chatbot.generator is generator
    assert chatbot.gate is gate
    assert loaded == [
        (
            "generator",
            Path("generator"),
            {"device": "cuda", "compute_type": "int8_float16"},
        ),
        (
            "gate",
            Path("gate"),
            {"device": "cuda", "compute_type": "int8_float16"},
        ),
    ]


def test_serve_log_level_defaults_to_info_and_accepts_debug() -> None:
    required = [
        "--model-dir",
        "generator",
        "--gate-model-dir",
        "gate",
    ]

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
