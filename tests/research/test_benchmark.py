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


def test_frozen_benchmark_is_balanced_and_executable() -> None:
    rows = load_benchmark()
    release = load_release()
    report = validate_benchmark(
        rows,
        load_ontology(),
        training_rows=release["train"] + release["val"],
    )

    assert report == {
        "records": 164,
        "targets": 80,
        "register_counts": {
            "colloquial": 41,
            "formal": 41,
            "neutral": 41,
            "noisy": 41,
        },
        "query_shape_counts": {
            "aggregate": 8,
            "aggregate_filter": 8,
            "direct": 78,
            "graph_hop": 54,
            "multi_column": 16,
        },
    }


def test_frozen_manifest_checksums_match() -> None:
    manifest_path = Path("resources/datasets/sparql_v1/manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for relative_path, expected in manifest["sha256"].items():
        payload = (manifest_path.parent / relative_path).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected


def test_reference_predictions_score_perfectly() -> None:
    rows = load_benchmark()
    report = evaluate_benchmark(
        rows,
        reference_predictions(rows),
        load_ontology(),
    )

    assert report["overall"]["answer_exact_rate"] == 1.0
    assert report["overall"]["canonical_query_exact_rate"] == 1.0
    assert report["prediction_file"] == {
        "missing_ids": [],
        "unexpected_ids": [],
    }


def test_benchmark_rejects_exact_training_leak() -> None:
    rows = load_benchmark()
    leaked = dict(rows[0])
    release = load_release()
    training_rows = release["train"] + release["val"]
    leaked["input"] = training_rows[0]["input"]

    with pytest.raises(BenchmarkError, match="leaks from training"):
        validate_benchmark([leaked], load_ontology(), training_rows=training_rows)
