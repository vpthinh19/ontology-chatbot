"""Convert a trained PhoBERT gate into a PyTorch-free runtime artifact."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Mapping

import numpy as np


TOKENIZER_FILES = (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.txt",
    "bpe.codes",
)

HEAD_KEYS = {
    "dense_weight": "classifier.dense.weight",
    "dense_bias": "classifier.dense.bias",
    "out_proj_weight": "classifier.out_proj.weight",
    "out_proj_bias": "classifier.out_proj.bias",
}


def convert_gate(
    source_dir: Path,
    output_dir: Path,
    *,
    quantization: str = "int8",
) -> dict:
    """Export the CT2 encoder, NumPy classifier head, and runtime manifest."""
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    source_model_dir = source_dir / "model"
    source_manifest = _load_source_manifest(source_dir / "manifest.json")
    if not (source_model_dir / "config.json").is_file():
        raise FileNotFoundError(f"gate checkpoint not found: {source_model_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"gate output directory is not empty: {output_dir}")

    try:
        import ctranslate2
        from ctranslate2.converters import TransformersConverter
        from transformers import AutoModelForSequenceClassification
    except ImportError as exc:  # pragma: no cover - CLI dependency boundary.
        raise RuntimeError("install the train extra to convert the domain gate") from exc

    model = AutoModelForSequenceClassification.from_pretrained(
        source_model_dir,
        local_files_only=True,
    )
    classifier = _classifier_arrays(model.state_dict())

    converter = TransformersConverter(
        str(source_model_dir),
        low_cpu_mem_usage=True,
    )
    converter.convert(
        str(output_dir),
        quantization=quantization,
        force=False,
    )
    for name in TOKENIZER_FILES:
        source = source_model_dir / name
        if source.is_file():
            shutil.copy2(source, output_dir / name)
    np.savez(output_dir / "classifier.npz", **classifier)

    manifest = {
        "format": "ctranslate2-domain-gate",
        "ctranslate2_version": ctranslate2.__version__,
        "quantization": quantization,
        "source": str(source_dir),
        "model_id": source_manifest.get("model_id"),
        "revision": source_manifest.get("revision"),
        "threshold": source_manifest["threshold"],
        "label_to_id": source_manifest["label_to_id"],
        "classifier": {
            "file": "classifier.npz",
            "input": "cls",
            "activation": "tanh",
        },
        "files": {
            path.name: _sha256(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _load_source_manifest(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"gate manifest not found: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected_labels = {"out_of_scope": 0, "in_scope": 1}
    if manifest.get("label_to_id") != expected_labels:
        raise ValueError(f"label_to_id must be {expected_labels}")
    threshold = manifest.get("threshold")
    if not isinstance(threshold, (int, float)) or not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0 and 1")
    return manifest


def _classifier_arrays(state: Mapping[str, object]) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for output_name, state_name in HEAD_KEYS.items():
        if state_name not in state:
            raise ValueError(f"gate checkpoint is missing {state_name}")
        value = state[state_name]
        if hasattr(value, "detach"):
            value = value.detach().float().cpu().numpy()
        arrays[output_name] = np.asarray(value, dtype=np.float32)
    hidden_size = arrays["dense_bias"].shape[0]
    expected_shapes = {
        "dense_weight": (hidden_size, hidden_size),
        "dense_bias": (hidden_size,),
        "out_proj_weight": (2, hidden_size),
        "out_proj_bias": (2,),
    }
    for name, shape in expected_shapes.items():
        if arrays[name].shape != shape:
            raise ValueError(
                f"unexpected classifier shape for {name}: "
                f"{arrays[name].shape}, expected {shape}"
            )
    return arrays


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
