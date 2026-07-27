import json

from ontchatbot.research.dataset import load_release
from ontchatbot.research.reporting import (
    build_dataset_report,
    build_model_report,
    sha256_file,
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

    assert report["dataset"]["records"] == 1416
    assert report["dataset"]["queries"] == 215
    assert report["in_domain_contract"] == {
        "train_queries": 215,
        "validation_queries_supported_by_train": 215,
        "validation_queries": 215,
        "test_queries_supported_by_train": 215,
        "test_queries": 215,
    }
    assert report["ontology"]["resources_missing_vietnamese_label"] == []
    assert set(report["dataset"]["query_features_by_split"]) == {
        "train",
        "val",
        "test",
    }
    assert report["training_readiness"] == {"ready": True, "gaps": []}

    write_public_reports(report, output_dir=tmp_path)
    assert (tmp_path / "dataset.json").is_file()
    assert (tmp_path / "figures/dataset-splits.svg").is_file()
    assert (tmp_path / "figures/registers.svg").is_file()
    assert (tmp_path / "figures/query-features.svg").is_file()


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
    assert report["models"]["bartpho"]["inference"]["records"] == 215
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
