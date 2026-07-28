from __future__ import annotations

import json
from pathlib import Path

from ontchatbot.research.gate_dataset import (
    load_gate_release,
    validate_gate_release,
)
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.settings import DATASET_DIR, GATE_DIR, RESOURCES


def _normalized(text: str) -> str:
    return normalize_model_input(text).casefold()


def test_dataset_releases_use_named_subdirectories() -> None:
    assert DATASET_DIR == RESOURCES / "dataset" / "main"
    assert GATE_DIR == RESOURCES / "dataset" / "gate"
    assert not (RESOURCES / "gate").exists()


def test_gate_release_is_balanced_and_contains_every_supported_question() -> None:
    release = load_gate_release(GATE_DIR)

    report = validate_gate_release(release)

    assert report["valid"] is True, report["errors"][:10]
    for split in ("train", "val", "test"):
        source_rows = [
            json.loads(line)
            for line in (DATASET_DIR / f"{split}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        positives = {
            _normalized(row["input"])
            for row in release[split]
            if row["label"] == "in_scope"
        }
        assert positives == {_normalized(row["input"]) for row in source_rows}
        assert report["splits"][split]["in_scope"] == len(source_rows)
        assert report["splits"][split]["out_of_scope"] == len(source_rows)


def test_gate_manifest_matches_validated_release() -> None:
    release = load_gate_release(GATE_DIR)
    report = validate_gate_release(release)
    manifest = json.loads((GATE_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["records"] == report["records"]
    assert manifest["splits"] == report["splits"]
    assert set(manifest["sha256"]) == {"train.jsonl", "val.jsonl", "test.jsonl"}
    for name, expected in manifest["sha256"].items():
        import hashlib

        actual = hashlib.sha256((GATE_DIR / name).read_bytes()).hexdigest()
        assert actual == expected
