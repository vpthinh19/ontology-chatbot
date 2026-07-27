import hashlib
import json
from pathlib import Path

import pytest

from ontchatbot.research.benchmark import (
    BenchmarkError,
    evaluate_benchmark,
    load_benchmark,
    reference_predictions,
    validate_benchmark,
)
from ontchatbot.research.dataset import load_release
from ontchatbot.runtime.sparql import load_ontology


def test_test_set_is_held_out_balanced_and_executable() -> None:
    rows = load_benchmark()
    release = load_release()
    report = validate_benchmark(
        rows,
        load_ontology(),
        training_rows=release["train"] + release["val"],
    )

    assert report == {
        "records": 168,
        "targets": 42,
        "register_counts": {
            "colloquial": 42,
            "formal": 42,
            "neutral": 42,
            "noisy": 42,
        },
        "targets_seen_in_model_selection_data": 0,
        "schema_terms_missing_from_training": [],
    }


def test_manifest_checksums_match() -> None:
    manifest_path = Path("resources/dataset/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for item in manifest["files"].values():
        payload = (manifest_path.parent / item["path"]).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == item["sha256"]
    ontology = manifest_path.parent / manifest["ontology"]["path"]
    assert hashlib.sha256(ontology.read_bytes()).hexdigest() == manifest["ontology"]["sha256"]


def test_reference_predictions_score_perfectly() -> None:
    rows = load_benchmark()
    report = evaluate_benchmark(rows, reference_predictions(rows), load_ontology())

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["canonical_query_exact_rate"] == 1.0
    assert report["prediction_file"] == {"missing_ids": [], "unexpected_ids": []}


def test_benchmark_rejects_training_question_leak() -> None:
    rows = load_benchmark()
    leaked = dict(rows[0])
    release = load_release()
    training_rows = release["train"] + release["val"]
    leaked["input"] = training_rows[0]["input"]

    with pytest.raises(BenchmarkError, match="leaks from training"):
        validate_benchmark([leaked], load_ontology(), training_rows=training_rows)
