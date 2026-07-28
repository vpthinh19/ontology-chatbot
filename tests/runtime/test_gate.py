from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

from ontchatbot.runtime.gate import CTranslate2DomainGate


class _Tokenizer:
    def __init__(self) -> None:
        self.source: str | None = None

    def __call__(self, source: str, **kwargs) -> SimpleNamespace:
        self.source = source
        assert kwargs == {
            "add_special_tokens": True,
            "max_length": 128,
            "truncation": True,
        }
        return SimpleNamespace(input_ids=[0, 1, 2])

    def convert_ids_to_tokens(self, ids: list[int]) -> list[str]:
        assert ids == [0, 1, 2]
        return ["<s>", "sinh", "viên"]


class _Encoder:
    def __init__(self) -> None:
        self.tokens: list[list[str]] | None = None

    def forward_batch(self, tokens: list[list[str]]) -> SimpleNamespace:
        self.tokens = tokens
        return SimpleNamespace(
            last_hidden_state=np.asarray(
                [[[1.0, 2.0], [99.0, 99.0], [99.0, 99.0]]],
                dtype=np.float32,
            )
        )


def _classifier() -> dict[str, np.ndarray]:
    return {
        "dense_weight": np.eye(2, dtype=np.float32),
        "dense_bias": np.zeros(2, dtype=np.float32),
        "out_proj_weight": np.asarray([[-1.0, 0.0], [1.0, 0.0]], dtype=np.float32),
        "out_proj_bias": np.zeros(2, dtype=np.float32),
    }


def test_gate_normalizes_input_and_applies_phobert_classifier_to_cls() -> None:
    encoder = _Encoder()
    tokenizer = _Tokenizer()
    gate = CTranslate2DomainGate(encoder, tokenizer, _classifier(), threshold=0.8)

    decision = gate.decide("  sv   dky  ")

    expected_probability = 1.0 / (1.0 + math.exp(-2.0 * math.tanh(1.0)))
    assert tokenizer.source == "sinh viên đăng ký"
    assert encoder.tokens == [["<s>", "sinh", "viên"]]
    assert decision.probability == pytest.approx(expected_probability)
    assert decision.accepted is True


def test_gate_rejects_empty_normalized_input() -> None:
    gate = CTranslate2DomainGate(_Encoder(), _Tokenizer(), _classifier(), threshold=0.8)

    with pytest.raises(ValueError, match="empty"):
        gate.decide("   ")


def _write_artifact(root: Path) -> dict:
    root.mkdir()
    (root / "model.bin").write_bytes(b"encoder")
    (root / "config.json").write_text("{}", encoding="utf-8")
    (root / "tokenizer_config.json").write_text("{}", encoding="utf-8")
    np.savez(root / "classifier.npz", **_classifier())
    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.iterdir())
    }
    manifest = {
        "format": "ctranslate2-domain-gate",
        "threshold": 0.8,
        "label_to_id": {"out_of_scope": 0, "in_scope": 1},
        "classifier": {
            "file": "classifier.npz",
            "input": "cls",
            "activation": "tanh",
        },
        "files": files,
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def _install_runtime_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    ctranslate2 = ModuleType("ctranslate2")
    ctranslate2.Encoder = lambda *args, **kwargs: _Encoder()

    class FakeAutoTokenizer:
        @classmethod
        def from_pretrained(cls, *args, **kwargs) -> _Tokenizer:
            assert kwargs == {"local_files_only": True}
            return _Tokenizer()

    transformers = ModuleType("transformers")
    transformers.AutoTokenizer = FakeAutoTokenizer
    monkeypatch.setitem(sys.modules, "ctranslate2", ctranslate2)
    monkeypatch.setitem(sys.modules, "transformers", transformers)


def test_gate_loads_threshold_and_verified_numpy_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "gate"
    _write_artifact(artifact)
    _install_runtime_dependencies(monkeypatch)

    gate = CTranslate2DomainGate.load(artifact)

    assert gate.decide("sv dky").accepted is True


def test_gate_load_rejects_checksum_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "gate"
    _write_artifact(artifact)
    (artifact / "classifier.npz").write_bytes(b"corrupted")
    _install_runtime_dependencies(monkeypatch)

    with pytest.raises(ValueError, match="checksum"):
        CTranslate2DomainGate.load(artifact)
