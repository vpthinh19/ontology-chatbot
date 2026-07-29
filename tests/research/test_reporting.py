import json

from ontchatbot.research.dataset import load_release
from ontchatbot.research.reporting import (
    _build_training_readiness,
    build_dataset_report,
    build_model_report,
    sha256_file,
    write_manifest,
    write_public_reports,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import DATASET_DIR


def _set_suite_count(directory, filename: str, count: int) -> None:
    path = directory / filename
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["overall"]["count"] = count
    metrics["inference"]["records"] = count
    path.write_text(json.dumps(metrics), encoding="utf-8")


def test_public_dataset_report_matches_contract(tmp_path) -> None:
    report = build_dataset_report(load_release(), load_ontology())

    assert report["dataset"]["records"] == 2000
    assert report["dataset"]["query_families"] == 51
    assert report["dataset"]["catalogue_families"] == 51
    assert report["dataset"]["domains"]["procedure"] > 0
    assert report["dataset"]["domains"]["out-of-domain"] > 0
    assert report["in_domain_contract"] == {
        "train_queries": 51,
        "validation_queries_supported_by_train": 51,
        "validation_queries": 51,
        "test_queries_supported_by_train": 51,
        "test_queries": 51,
    }
    assert report["ontology"]["resources_missing_vietnamese_label"] == []
    assert set(report["dataset"]["query_features_by_split"]) == {
        "train",
        "val",
        "test",
    }
    assert report["training_readiness"]["ready"] is True
    gap_codes = {
        gap["code"] for gap in report["training_readiness"]["gaps"]
    }
    assert gap_codes == set()
    assert report["coverage"]["complete"] is True
    assert report["sha256"]["catalogue.jsonl"]
    assert report["sha256"]["coverage.json"]

    write_public_reports(report, output_dir=tmp_path)
    assert (tmp_path / "dataset.json").is_file()
    assert (tmp_path / "figures/dataset-splits.svg").is_file()
    assert (tmp_path / "figures/registers.svg").is_file()
    assert (tmp_path / "figures/query-features.svg").is_file()


def test_training_readiness_reports_missing_finite_slot_values() -> None:
    release = {
        "train": [
            {"query_id": "query-0001", "register": "formal"},
            {"query_id": "query-0001", "register": "neutral"},
        ],
        "val": [{"query_id": "query-0001", "register": "colloquial"}],
        "test": [{"query_id": "query-0001", "register": "noisy"}],
    }
    validation = {
        "slot_coverage": {
            "query-0001": {
                "entity": {
                    "declared": [":One", ":Two"],
                    "seen_train": [":One"],
                    "missing_train": [":Two"],
                }
            }
        }
    }

    report = _build_training_readiness(release, validation)

    assert report["ready"] is False
    assert report["finite_slots_missing_from_train"] == [
        {"query_id": "query-0001", "slot": "entity", "values": [":Two"]}
    ]


def test_manifest_declares_per_query_split_cardinality(tmp_path) -> None:
    report = build_dataset_report(load_release(), load_ontology())
    path = tmp_path / "manifest.json"

    write_manifest(report, path)

    contract = json.loads(path.read_text(encoding="utf-8"))["split_contract"]
    assert contract["train_min_rows_per_query"] == 4
    assert contract["train_registers_per_query"] == 4
    assert contract["val_min_rows_per_query"] == 2
    assert contract["test_min_rows_per_query"] == 2
    assert contract["held_out_min_registers_per_query"] == 2
    assert contract["catalogue_path"] == "catalogue.jsonl"
    assert json.loads(path.read_text(encoding="utf-8"))["coverage"] == {
        "path": "coverage.json",
        "sha256": report["sha256"]["coverage.json"],
    }


def test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path) -> None:
    release = load_release()
    manifest_sha256 = sha256_file(DATASET_DIR / "manifest.json")
    for name in ("bartpho", "vit5", "t5gemma2"):
        directory = tmp_path / name
        (directory / "model").mkdir(parents=True)
        (directory / "model" / "config.json").write_text("{}", encoding="utf-8")
        (directory / "metrics.json").write_text(
            json.dumps(
                {
                    "overall": {"count": 2, "answer_exact_rate": 0.0},
                    "training": {
                        "model_id": name,
                        "train_records": 10,
                        "train_runtime_seconds": 12.5,
                        "peak_vram_bytes": 100,
                        "dataset_manifest_sha256": manifest_sha256,
                    },
                    "training_log": [
                        {"epoch": 1.0, "loss": 1.0},
                        {"epoch": 1.0, "eval_answer_exact_rate": 0.25},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (directory / "validation_metrics.json").write_text(
            json.dumps(
                {
                    "overall": {
                        "count": len(release["val"]),
                        "answer_exact_rate": 0.5,
                    },
                    "inference": {
                        "records": len(release["val"]),
                        "seconds": 1.0,
                    },
                    "artifact_evaluation": {
                        "backend": "transformers",
                        "load_method": "from_pretrained",
                        "model": name,
                        "suite": "validation",
                        "dataset_manifest_sha256": manifest_sha256,
                    },
                }
            ),
            encoding="utf-8",
        )
        (directory / "benchmark_metrics.json").write_text(
            json.dumps(
                {
                    "overall": {
                        "count": len(release["test"]),
                        "answer_exact_rate": 0.4,
                    },
                    "by_register": {},
                    "by_query_feature": {},
                    "error_counts": {},
                    "inference": {
                        "records": len(release["test"]),
                        "seconds": 1.0,
                    },
                    "artifact_evaluation": {
                        "backend": "transformers",
                        "load_method": "from_pretrained",
                        "model": name,
                        "suite": "benchmark",
                        "dataset_manifest_sha256": manifest_sha256,
                    },
                }
            ),
            encoding="utf-8",
        )

    report = build_model_report(tmp_path)

    assert report is not None
    assert report["models"]["bartpho"]["validation"]["answer_exact_rate"] == 0.5
    assert report["models"]["bartpho"]["inference"]["records"] == len(release["val"])
    assert report["models"]["bartpho"]["training"][
        "artifact_roundtrip_verified"
    ] is True


def test_model_report_rejects_missing_artifact_evaluation_provenance(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    path = tmp_path / "vit5" / "benchmark_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    del metrics["artifact_evaluation"]
    path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_different_benchmark_sizes(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    path = tmp_path / "t5gemma2" / "benchmark_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["overall"]["count"] = 3
    metrics["inference"]["records"] = 3
    path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_metrics_for_a_different_dataset_size(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    for name in ("bartpho", "vit5", "t5gemma2"):
        directory = tmp_path / name
        _set_suite_count(directory, "validation_metrics.json", 2)
        _set_suite_count(directory, "benchmark_metrics.json", 2)

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_missing_dataset_provenance(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    for name in ("bartpho", "vit5", "t5gemma2"):
        directory = tmp_path / name
        for filename in ("validation_metrics.json", "benchmark_metrics.json"):
            path = directory / filename
            metrics = json.loads(path.read_text(encoding="utf-8"))
            del metrics["artifact_evaluation"]["dataset_manifest_sha256"]
            path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_missing_training_dataset_provenance(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    path = tmp_path / "bartpho" / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    del metrics["training"]["dataset_manifest_sha256"]
    path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_mismatched_training_dataset_provenance(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    path = tmp_path / "bartpho" / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["training"]["dataset_manifest_sha256"] = "stale-manifest"
    path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None
