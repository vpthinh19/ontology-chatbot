from __future__ import annotations

import json
from pathlib import Path

import pytest

from ontchatbot.research.consistency import (
    CANONICAL_INPUT_NAMES,
    ArtifactPaths,
    ConsistencyError,
    ConsistencySnapshot,
    build_consistency_snapshot,
    classify_provenance,
    compare_committed_artifacts,
    require_consistent,
)
from ontchatbot.cli import validate_data
from ontchatbot.research.reporting import sha256_file, write_consistency_snapshot
from ontchatbot.settings import (
    ANSWER_INVENTORY_PATH,
    DATASET_DIR,
    PROJECT_ROOT,
    QUERY_CATALOGUE_PATH,
    REPORTS_DIR,
)


def test_matching_complete_fingerprint_is_current() -> None:
    inputs = {name: "a" * 64 for name in CANONICAL_INPUT_NAMES}

    assert classify_provenance(inputs, dict(inputs)) == "current"


def test_changed_complete_fingerprint_is_stale() -> None:
    baseline = {name: "a" * 64 for name in CANONICAL_INPUT_NAMES}
    current = dict(baseline)
    current["ontology.ttl"] = "b" * 64

    assert classify_provenance(baseline, current) == "stale"


def test_missing_baseline_fingerprint_is_unverified() -> None:
    current = {name: "a" * 64 for name in CANONICAL_INPUT_NAMES}

    assert classify_provenance({}, current) == "unverified"


def test_canonical_snapshot_covers_the_complete_chain() -> None:
    snapshot = build_consistency_snapshot()

    # Đối chiếu với chính danh mục khả năng trả lời; số mục được suy ra từ
    # snapshot để phạm vi kiểm tra thay đổi cùng dữ liệu.
    entries = len(snapshot.inventory["entries"])

    assert entries
    assert 0 < snapshot.catalogue_validation["supported_entries"] <= entries
    assert (
        snapshot.catalogue_validation["covered_entries"]
        == snapshot.catalogue_validation["supported_entries"]
    )
    assert snapshot.catalogue_validation["uncovered_entries"] == []
    assert snapshot.dataset_report["training_readiness"]["ready"] is True
    assert snapshot.dataset_report["validation"]["catalogue_coverage_required"] is True
    # Chỉ số model có thể là "stale" khi fingerprint của dữ liệu khác checkpoint;
    # trạng thái này biểu thị cần đánh giá lại, không phải lỗi snapshot.
    assert snapshot.provenance["model_metrics"]["status"] in ("current", "stale")


def test_artifact_comparison_reports_only_the_changed_stage(tmp_path) -> None:
    snapshot = build_consistency_snapshot()
    paths = _copy_artifacts(tmp_path, snapshot)
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    manifest["totals"]["records"] += 1
    paths.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    mismatches = compare_committed_artifacts(snapshot, paths=paths)

    assert mismatches == [
        {
            "stage": "manifest",
            "path": str(paths.manifest),
            "action": "regenerate derived artifacts",
        }
    ]
    with pytest.raises(ConsistencyError, match="manifest") as caught:
        require_consistent(mismatches)
    assert str(paths.manifest) in str(caught.value)


def test_validation_cli_does_not_write_derived_artifacts(monkeypatch, capsys) -> None:
    paths = _canonical_artifacts()
    before = {name: sha256_file(path) for name, path in paths.__dict__.items()}
    monkeypatch.setattr("sys.argv", ["validate_sparql_dataset"])

    validate_data.main()
    capsys.readouterr()

    after = {name: sha256_file(path) for name, path in paths.__dict__.items()}
    assert after == before


def test_snapshot_generation_round_trips_without_changing_inputs(tmp_path) -> None:
    paths = _temporary_artifacts(tmp_path)
    paths.provenance.write_bytes(
        (REPORTS_DIR / "provenance.json").read_bytes()
    )
    protected = _canonical_input_paths()
    before = {name: sha256_file(path) for name, path in protected.items()}
    snapshot = build_consistency_snapshot(paths=paths)

    write_consistency_snapshot(
        snapshot,
        paths=paths,
        reports_dir=tmp_path / "reports",
    )

    expected = {
        "inventory": snapshot.inventory,
        "manifest": snapshot.manifest,
        "dataset_report": snapshot.dataset_report,
        "procedure_report": snapshot.procedure_report,
        "provenance": snapshot.provenance,
    }
    for name, path in paths.__dict__.items():
        assert json.loads(path.read_text(encoding="utf-8")) == expected[name]
    assert {name: sha256_file(path) for name, path in protected.items()} == before
    assert (tmp_path / "reports/figures/dataset-splits.svg").is_file()


def test_generation_preserves_stale_baseline_and_updates_current_inputs(
    tmp_path,
) -> None:
    paths = _temporary_artifacts(tmp_path)
    baseline = json.loads(
        (REPORTS_DIR / "provenance.json").read_text(encoding="utf-8")
    )
    baseline["baseline_inputs"]["ontology.ttl"] = "a" * 64
    paths.provenance.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    snapshot = build_consistency_snapshot(paths=paths)

    write_consistency_snapshot(
        snapshot,
        paths=paths,
        reports_dir=tmp_path / "reports",
    )

    generated = json.loads(paths.provenance.read_text(encoding="utf-8"))
    assert generated["baseline_inputs"]["ontology.ttl"] == "a" * 64
    assert generated["current_inputs"]["ontology.ttl"] == sha256_file(
        PROJECT_ROOT / "resources/ontology/ontology.ttl"
    )
    assert generated["model_metrics"]["status"] == "stale"
    assert generated["deployment_metrics"]["status"] == "stale"


def _copy_artifacts(
    root: Path,
    snapshot: ConsistencySnapshot,
) -> ArtifactPaths:
    destinations = ArtifactPaths(
        inventory=root / "answer_inventory.json",
        manifest=root / "manifest.json",
        dataset_report=root / "dataset.json",
        procedure_report=root / "procedure-dataset.json",
        provenance=root / "provenance.json",
    )
    payloads = {
        "inventory": snapshot.inventory,
        "manifest": snapshot.manifest,
        "dataset_report": snapshot.dataset_report,
        "procedure_report": snapshot.procedure_report,
        "provenance": snapshot.provenance,
    }
    for name, destination in destinations.__dict__.items():
        destination.write_text(
            json.dumps(payloads[name], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return destinations


def _temporary_artifacts(root: Path) -> ArtifactPaths:
    reports = root / "reports"
    reports.mkdir(parents=True)
    return ArtifactPaths(
        inventory=root / "resources/ontology/answer_inventory.json",
        manifest=root / "resources/dataset/manifest.json",
        dataset_report=reports / "dataset.json",
        procedure_report=reports / "procedure-dataset.json",
        provenance=reports / "provenance.json",
    )


def _canonical_input_paths() -> dict[str, Path]:
    return {
        "ontology.ttl": PROJECT_ROOT / "resources/ontology/ontology.ttl",
        "catalogue.jsonl": QUERY_CATALOGUE_PATH,
        "coverage.json": DATASET_DIR / "coverage.json",
        "train.jsonl": DATASET_DIR / "train.jsonl",
        "val.jsonl": DATASET_DIR / "val.jsonl",
        "test.jsonl": DATASET_DIR / "test.jsonl",
    }


def _canonical_artifacts() -> ArtifactPaths:
    reports = REPORTS_DIR
    return ArtifactPaths(
        inventory=ANSWER_INVENTORY_PATH,
        manifest=DATASET_DIR / "manifest.json",
        dataset_report=reports / "dataset.json",
        procedure_report=reports / "procedure-dataset.json",
        provenance=reports / "provenance.json",
    )
