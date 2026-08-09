import json

from ontchatbot.catalogue import load_catalogue
from ontchatbot.research.dataset import load_release
from ontchatbot.research.reporting import (
    _build_training_readiness,
    build_dataset_report,
    build_manifest,
    build_model_report,
    build_procedure_dataset_report,
    sha256_file,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import (
    DATASET_DIR,
    ONTOLOGY_PATH,
    PROJECT_ROOT,
    QUERY_CATALOGUE_PATH,
)


def _set_suite_count(directory, filename: str, count: int) -> None:
    path = directory / filename
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["overall"]["count"] = count
    if "inference" in metrics:
        metrics["inference"]["records"] = count
    path.write_text(json.dumps(metrics), encoding="utf-8")


def test_public_dataset_report_matches_contract(tmp_path) -> None:
    report = build_dataset_report(load_release(), load_ontology())

    # Đối chiếu với artifact thật, KHÔNG chốt cứng con số: bản trước chốt 4.454
    # dòng / 51 họ, nên khi dataset được sinh lại nó khoá cái sai lại thay vì
    # phát hiện ra.
    release = load_release()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    trained = {
        row["query_id"] for rows in release.values() for row in rows
    }

    assert report["dataset"]["records"] == sum(len(r) for r in release.values())
    assert report["dataset"]["query_families"] == len(trained)
    assert report["dataset"]["catalogue_families"] == len(catalogue)
    assert report["dataset"]["domains"]["procedure"] > 0
    assert report["dataset"]["domains"]["out-of-domain"] > 0
    # Mọi họ xuất hiện ở val/test đều phải được dạy ở train - nếu không thì tập
    # chấm đang đo một thứ model chưa từng thấy hình dạng.
    contract = report["in_domain_contract"]
    assert contract["validation_queries_supported_by_train"] == contract["validation_queries"]
    assert contract["test_queries_supported_by_train"] == contract["test_queries"]
    assert contract["train_queries"] >= contract["validation_queries"]
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

    # Đối chiếu ARTIFACT THẬT do ``generate_reports`` ghi ra, không phải một bản
    # tạm do chính test dựng. Hai đường ghi cũ (``write_public_reports``,
    # ``write_manifest``) đã bị bỏ: ``write_consistency_snapshot`` ghi cả năm
    # artifact cùng lúc từ một ảnh chụp đã kiểm chứng, còn giữ đường ghi song
    # song là giữ một cách sinh ra manifest lệch với báo cáo.
    reports = PROJECT_ROOT / "reports"
    assert (reports / "dataset.json").is_file()
    assert (reports / "figures/dataset-splits.svg").is_file()
    assert (reports / "figures/registers.svg").is_file()
    assert (reports / "figures/query-features.svg").is_file()


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


def test_manifest_declares_per_query_split_cardinality() -> None:
    """Manifest thật phải khai hợp đồng chia tập, không phải một bản tạm."""

    contract = json.loads(
        (DATASET_DIR / "manifest.json").read_text(encoding="utf-8")
    )["split_contract"]
    assert contract["train_min_rows_per_query"] == 4
    assert contract["train_registers_per_query"] == 4
    assert contract["val_min_rows_per_query"] == 2
    assert contract["test_min_rows_per_query"] == 2
    assert contract["held_out_min_registers_per_query"] == 2
    assert contract["catalogue_path"] == "catalogue.jsonl"
    manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["coverage"] == {
        "path": "coverage.json",
        "sha256": sha256_file(DATASET_DIR / "coverage.json"),
    }


def test_manifest_ontology_path_resolves_from_manifest_directory(tmp_path) -> None:
    resources = tmp_path / "resources"
    dataset_dir = resources / "dataset"
    ontology_dir = resources / "ontology"
    dataset_dir.mkdir(parents=True)
    ontology_dir.mkdir(parents=True)
    ontology_path = ontology_dir / "ontology.ttl"
    ontology_path.write_bytes(ONTOLOGY_PATH.read_bytes())
    report = build_dataset_report(
        load_release(),
        load_ontology(),
        ontology_path=ontology_path,
    )
    manifest_path = dataset_dir / "manifest.json"

    manifest = build_manifest(
        report,
        manifest_path=manifest_path,
        ontology_path=ontology_path,
    )

    assert manifest["ontology"]["path"] == "../ontology/ontology.ttl"
    assert (
        manifest_path.parent / manifest["ontology"]["path"]
    ).resolve() == ontology_path.resolve()
    assert manifest["ontology"]["sha256"] == sha256_file(ontology_path)


def test_procedure_report_is_derived_from_release() -> None:
    report = build_procedure_dataset_report(load_release(), dataset_dir=DATASET_DIR)

    # Bản trước chốt 142 đích quy trình. Danh mục v2 đổi tiền tố họ từ
    # ``procedure-`` sang ``academic-procedure-`` nên phép đếm cũ tụt còn 42 -
    # đó là đổi TÊN, không phải mất dữ liệu. Đối chiếu với release thật.
    assert report["scope"] == "academic-procedure"
    assert report["procedure_target_count"] > 0
    assert report["instruction_target_count"] > 0
    for split in ("train", "val", "test"):
        assert report["splits"][split]["procedure_records"] > 0
    assert report["splits"]["train"]["procedure_records"] > (
        report["splits"]["val"]["procedure_records"]
    )
    assert set(report["contracts"]) == {
        "every_primary_procedure_family_is_taught",
        "every_procedure_family_has_all_four_registers",
        "every_evaluated_target_was_taught",
        "every_procedure_has_a_step_by_step_question",
        "every_procedure_also_has_an_overview_question",
        "every_instruction_target_has_a_direct_question",
        "course_registration_instruction_samples",
        "both_question_types_are_evaluated_in_val",
        "both_question_types_are_evaluated_in_test",
    }
    assert all(
        value is True
        for key, value in report["contracts"].items()
        if isinstance(value, bool)
    )


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
                    "overall": {
                        "count": len(release["val"]),
                        "answer_exact_rate": 0.5,
                    },
                    "training": {
                        "model_id": name,
                        "train_records": 10,
                        "train_runtime_seconds": 12.5,
                        "peak_vram_bytes": 100,
                        "dataset_manifest_sha256": manifest_sha256,
                        "merged_artifact": True,
                    },
                    "training_log": [
                        {"epoch": 1.0, "loss": 1.0},
                        {"epoch": 1.0, "eval_answer_exact_rate": 0.25},
                    ],
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
                        "system_answer_exact_rate": 0.45,
                        "result_f1": 0.42,
                    },
                    "by_register": {},
                    "by_query_feature": {},
                    "error_counts": {},
                }
            ),
            encoding="utf-8",
        )

    report = build_model_report(tmp_path)

    assert report is not None
    assert report["models"]["bartpho"]["validation"]["answer_exact_rate"] == 0.5
    assert report["models"]["bartpho"]["training"]["merged_artifact"] is True


def test_model_report_rejects_unmerged_artifact(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    path = tmp_path / "vit5" / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["training"]["merged_artifact"] = False
    path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_different_benchmark_sizes(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    path = tmp_path / "t5gemma2" / "benchmark_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["overall"]["count"] = 3
    path.write_text(json.dumps(metrics), encoding="utf-8")

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_metrics_for_a_different_dataset_size(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    for name in ("bartpho", "vit5", "t5gemma2"):
        directory = tmp_path / name
        _set_suite_count(directory, "metrics.json", 2)
        _set_suite_count(directory, "benchmark_metrics.json", 2)

    assert build_model_report(tmp_path) is None


def test_model_report_rejects_missing_model_artifact(tmp_path) -> None:
    test_model_report_uses_independently_reloaded_artifact_metrics(tmp_path)
    (tmp_path / "vit5" / "model" / "config.json").unlink()

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
