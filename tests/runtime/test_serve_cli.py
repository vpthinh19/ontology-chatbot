from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ontchatbot.cli.serve import _load_chatbot, _parse_args


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
