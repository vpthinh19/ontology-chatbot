"""CTranslate2 runtime for the ontology-domain gate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol

import numpy as np

from .text import normalize_model_input

MAX_GATE_LENGTH = 128


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    probability: float


class DomainGate(Protocol):
    @property
    def threshold(self) -> float: ...

    def decide(self, text: str) -> GateDecision: ...


class CTranslate2DomainGate:
    """Run a CT2 PhoBERT encoder and its exported NumPy classifier head."""

    def __init__(
        self,
        encoder,
        tokenizer,
        classifier: Mapping[str, np.ndarray],
        *,
        threshold: float,
        in_scope_id: int = 1,
    ) -> None:
        self._encoder = encoder
        self._tokenizer = tokenizer
        self._classifier = _validated_classifier(classifier)
        self._threshold = float(threshold)
        self._in_scope_id = in_scope_id
        if not 0.0 <= self._threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

    @property
    def threshold(self) -> float:
        return self._threshold

    @classmethod
    def load(
        cls,
        model_dir: Path,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> CTranslate2DomainGate:
        try:
            import ctranslate2
            from transformers import AutoTokenizer
        except ImportError as exc:  # pragma: no cover - inference dependency boundary.
            raise RuntimeError("install the inference extra to load the domain gate") from exc

        model_dir = Path(model_dir)
        manifest_path = model_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"domain gate manifest not found: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _validate_manifest(manifest)
        _verify_files(model_dir, manifest["files"])

        classifier_path = model_dir / manifest["classifier"]["file"]
        with np.load(classifier_path) as archive:
            classifier = {name: archive[name].copy() for name in archive.files}
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        encoder = ctranslate2.Encoder(
            str(model_dir),
            device=device,
            compute_type=compute_type,
        )
        return cls(
            encoder,
            tokenizer,
            classifier,
            threshold=manifest["threshold"],
            in_scope_id=manifest["label_to_id"]["in_scope"],
        )

    def decide(self, text: str) -> GateDecision:
        source = normalize_model_input(text)
        if not source:
            raise ValueError("question is empty")
        source_ids = self._tokenizer(
            source,
            add_special_tokens=True,
            max_length=MAX_GATE_LENGTH,
            truncation=True,
        ).input_ids
        source_tokens = self._tokenizer.convert_ids_to_tokens(source_ids)
        encoded = self._encoder.forward_batch([source_tokens])
        cls_state = np.asarray(encoded.last_hidden_state, dtype=np.float32)[0, 0]
        head = self._classifier
        hidden = np.tanh(cls_state @ head["dense_weight"].T + head["dense_bias"])
        logits = hidden @ head["out_proj_weight"].T + head["out_proj_bias"]
        logits = np.asarray(logits, dtype=np.float64)
        exponentials = np.exp(logits - logits.max())
        probability = float(exponentials[self._in_scope_id] / exponentials.sum())
        return GateDecision(
            accepted=probability >= self._threshold,
            probability=probability,
        )


def _validate_manifest(manifest: dict) -> None:
    if manifest.get("format") != "ctranslate2-domain-gate":
        raise ValueError("unsupported domain gate format")
    if manifest.get("label_to_id") != {"out_of_scope": 0, "in_scope": 1}:
        raise ValueError("invalid domain gate label_to_id")
    classifier = manifest.get("classifier")
    if classifier != {
        "file": "classifier.npz",
        "input": "cls",
        "activation": "tanh",
    }:
        raise ValueError("invalid domain gate classifier contract")
    threshold = manifest.get("threshold")
    if not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
        raise ValueError("invalid domain gate threshold")
    if not isinstance(manifest.get("files"), dict):
        raise ValueError("domain gate manifest has no file checksums")


def _validated_classifier(
    classifier: Mapping[str, np.ndarray],
) -> dict[str, np.ndarray]:
    required = {
        "dense_weight",
        "dense_bias",
        "out_proj_weight",
        "out_proj_bias",
    }
    if set(classifier) != required:
        raise ValueError("invalid classifier arrays")
    arrays = {name: np.asarray(value, dtype=np.float32) for name, value in classifier.items()}
    hidden_size = arrays["dense_bias"].shape[0]
    expected = {
        "dense_weight": (hidden_size, hidden_size),
        "dense_bias": (hidden_size,),
        "out_proj_weight": (2, hidden_size),
        "out_proj_bias": (2,),
    }
    if any(arrays[name].shape != shape for name, shape in expected.items()):
        raise ValueError("invalid classifier array shapes")
    return arrays


def _verify_files(model_dir: Path, checksums: Mapping[str, str]) -> None:
    for name, expected in checksums.items():
        path = model_dir / name
        if not path.is_file() or _sha256(path) != expected:
            raise ValueError(f"domain gate checksum mismatch: {name}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
