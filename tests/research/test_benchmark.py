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


def test_test_set_uses_only_train_supported_queries_and_is_executable() -> None:
    rows = load_benchmark()
    release = load_release()
    report = validate_benchmark(
        rows,
        load_ontology(),
        training_rows=release["train"],
    )

    assert report == {
        "records": 430,
        "queries": 215,
        "targets": 215,
        "register_counts": {
            "colloquial": 108,
            "formal": 107,
            "neutral": 108,
            "noisy": 107,
        },
        "queries_supported_by_train": 215,
        "targets_supported_by_train": 215,
    }


def test_manifest_checksums_match() -> None:
    manifest_path = Path("resources/dataset/main/manifest.json")
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
    training_rows = release["train"]
    leaked["input"] = training_rows[0]["input"]

    with pytest.raises(BenchmarkError, match="leaks from training"):
        validate_benchmark([leaked], load_ontology(), training_rows=training_rows)


def test_benchmark_rejects_query_not_supported_by_train() -> None:
    rows = load_benchmark()
    release = load_release()
    unsupported = {**rows[0], "query_id": "query-unsupported"}

    with pytest.raises(BenchmarkError, match="query IDs absent from train"):
        validate_benchmark(
            [unsupported],
            load_ontology(),
            training_rows=release["train"],
        )


def test_benchmark_rejects_target_not_supported_by_train() -> None:
    rows = load_benchmark()
    release = load_release()
    unsupported = {
        **rows[0],
        "target": 'SELECT ?answer WHERE { VALUES ?answer { "không có trong train" } }',
    }

    with pytest.raises(BenchmarkError, match="targets absent from train"):
        validate_benchmark(
            [unsupported],
            load_ontology(),
            training_rows=release["train"],
        )


def test_benchmark_rejects_mismatched_supported_query_and_target() -> None:
    rows = load_benchmark()
    release = load_release()
    mismatched = {**rows[0], "target": rows[1]["target"]}
    assert mismatched["query_id"] != rows[1]["query_id"]

    with pytest.raises(BenchmarkError, match="query-target pairs absent from train"):
        validate_benchmark(
            [mismatched],
            load_ontology(),
            training_rows=release["train"],
        )
