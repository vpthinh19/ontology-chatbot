"""Apply reviewed Stage B decisions to the editable SPARQL v2 draft."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..runtime.sparql import execute_select, load_ontology
from ..settings import PROJECT_ROOT
from .dataset import load_dataset, validate_dataset

SOURCE_DIR = PROJECT_ROOT / "resources/datasets/sparql_v1"
TARGET_DIR = PROJECT_ROOT / "resources/datasets/sparql_v2"
REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
ONTOLOGY_PATH = PROJECT_ROOT / "resources/ontology/ontology_v12.ttl"

MERGE_INTO = {
    "cap-036-f02": "cap-036-f01",
    "cap-049-f02": "cap-049-f01",
    "cap-052-f02": "cap-052-f01",
    "cap-058-f02": "cap-058-f01",
    "cap-046-f03": "cap-046-f01",
}

SPLIT_RECORDS = {"prod-0262": "cap-066-f04"}

TARGET_REWRITES = {
    "cap-011-f03": (
        'SELECT ?answer WHERE { :AcademicLeaveProcedure :condition ?answer . FILTER ( STR ( ?answer ) != "Bị ốm, thai sản hoặc tai nạn phải điều trị thời gian dài có giấy chứng nhận hợp lệ" ) }'
    ),
    "cap-012-f03": (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :hasDocument :StudyResumptionRequestForm . :StudyResumptionRequestForm rdfs:label ?answer . }"
    ),
    "cap-032-f02": (
        "SELECT ?answer WHERE { :MajorChangeProcedure :receivedBy ?node . ?node :phoneNumber ?answer . }"
    ),
    "cap-057-f03": (
        'SELECT ?answer WHERE { :K66TuitionBand3 :programName ?answer . FILTER ( STR ( ?answer ) != "Ô tô" ) }'
    ),
    "cap-061-f03": "SELECT DISTINCT ?answer WHERE { ?item :condition ?answer . }",
    "cap-063-f03": "SELECT DISTINCT ?answer WHERE { ?item :outcome ?answer . }",
}

SPLIT_TARGET = (
    "SELECT ?count ?answer WHERE { { SELECT (COUNT(DISTINCT ?node) AS ?count) "
    "WHERE { ?node a :TuitionRate . } } ?item a :TuitionRate . ?item rdfs:label ?answer . }"
)

INPUT_REWRITES = {
    "prod-0594": "Phòng tiếp nhận hồ sơ đổi ngành có số điện thoại nào để sinh viên liên hệ?",
    "prod-0829": "Hãy liệt kê toàn bộ điều kiện đang áp dụng cho các quy trình học vụ.",
    "prod-0830": "Các quy trình học vụ hiện có những điều kiện nào?",
    "prod-0831": "cho tui xem tất cả điều kiện của mấy quy trình học vụ với",
    "prod-0832": "liet ke tat ca dk cua cac quy trinh hoc vu",
    "prod-0845": "Hãy liệt kê toàn bộ kết quả có thể được ghi nhận sau các quy trình học vụ.",
    "prod-0846": "Các quy trình học vụ hiện có những kết quả nào?",
    "prod-0847": "cho tui xem hết mấy kết quả của các quy trình học vụ với",
    "prod-0848": "liet ke tat ca kq cua cac quy trinh hoc vu",
}

# These fixes needed an ontology/domain decision, not a row-level rewrite.
RESOLVED_WITHOUT_ROW_CHANGE = {
    "cap-014-f01",
    "cap-014-f02",
    "cap-014-f03",
    "cap-020-f01",
    "cap-020-f02",
    "cap-020-f03",
    "cap-021-f01",
    "cap-021-f02",
    "cap-021-f03",
    "cap-032-f01",
    "cap-032-f03",
    "cap-069-f01",
    "cap-069-f02",
    "cap-069-f03",
    "cap-071-f01",
    "cap-071-f02",
    "cap-071-f03",
    "cap-074-f01",
    "cap-074-f04",
    "count-graduation-conditions-01",
    "count-graduation-conditions-02",
    "count-graduation-conditions-03",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_decision_coverage(decisions: list[dict[str, Any]]) -> None:
    candidates = [row for row in decisions if row["v2_scope"] == "v2_candidate"]
    if len(candidates) != 237:
        raise ValueError(f"expected 237 v2 candidate families, got {len(candidates)}")

    expected_fixes = {
        row["family_id"] for row in candidates if row["reviewer_decision"] == "fix"
    }
    covered_fixes = set(TARGET_REWRITES) | RESOLVED_WITHOUT_ROW_CHANGE
    if expected_fixes != covered_fixes:
        raise ValueError(
            f"unresolved fix decisions: missing={sorted(expected_fixes - covered_fixes)}, "
            f"extra={sorted(covered_fixes - expected_fixes)}"
        )

    expected_merges = {
        row["family_id"] for row in candidates if row["reviewer_decision"] == "merge"
    }
    if expected_merges != set(MERGE_INTO):
        raise ValueError("merge decisions do not match the reviewed manifest")

    expected_splits = {
        row["family_id"] for row in candidates if row["reviewer_decision"] == "split"
    }
    if expected_splits != {"cap-066-f01"}:
        raise ValueError("split decisions do not match the reviewed manifest")


def build_draft() -> tuple[list[dict[str, str]], dict[str, Any], list[dict[str, Any]]]:
    decisions = _read_jsonl(REVIEW_DIR / "family_decisions.jsonl")
    _validate_decision_coverage(decisions)

    source_rows = load_dataset(SOURCE_DIR / "train.jsonl") + load_dataset(
        SOURCE_DIR / "val.jsonl"
    )
    if len(source_rows) != 948:
        raise ValueError(f"expected 948 train/val records, got {len(source_rows)}")

    draft: list[dict[str, str]] = []
    for source in source_rows:
        row = dict(source)
        original_family = row["family_id"]

        if row["id"] in SPLIT_RECORDS:
            row["family_id"] = SPLIT_RECORDS[row["id"]]
            row["target"] = SPLIT_TARGET
            row["query_shape"] = "aggregate"
        else:
            row["family_id"] = MERGE_INTO.get(original_family, original_family)
            if original_family in TARGET_REWRITES:
                row["target"] = TARGET_REWRITES[original_family]

        if row["id"] in INPUT_REWRITES:
            row["input"] = INPUT_REWRITES[row["id"]]
        draft.append(row)

    graph = load_ontology(ONTOLOGY_PATH)
    validation = validate_dataset(draft, graph)
    if validation["empty_result_ids"]:
        raise ValueError(f"empty target results: {validation['empty_result_ids']}")
    if validation["families"] != 233:
        raise ValueError(f"expected 233 families after merge/split, got {validation['families']}")

    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in draft:
        by_target[row["target"]].append(row)
    evidence = []
    for target, rows in sorted(by_target.items()):
        result = execute_select(graph, target)
        evidence.append(
            {
                "target": target,
                "family_ids": sorted({row["family_id"] for row in rows}),
                "record_ids": [row["id"] for row in rows],
                "result_count": len(result),
                "result": result,
            }
        )

    return draft, validation, evidence


def write_stage_b_artifacts() -> dict[str, Any]:
    draft, validation, evidence = build_draft()
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    draft_path = TARGET_DIR / "draft.jsonl"
    evidence_path = REVIEW_DIR / "target_evidence_v12.jsonl"
    manifest_path = REVIEW_DIR / "completion_manifest.json"

    _write_jsonl(draft_path, draft)
    _write_jsonl(evidence_path, evidence)

    manifest = {
        "stage": "B",
        "status": "complete",
        "source_release": "resources/datasets/sparql_v1",
        "source_files": {
            "train.jsonl": _sha256(SOURCE_DIR / "train.jsonl"),
            "val.jsonl": _sha256(SOURCE_DIR / "val.jsonl"),
        },
        "legacy_test_policy": "sparql_v1/test.jsonl is audit-only and is not copied into the v2 draft",
        "ontology": "resources/ontology/ontology_v12.ttl",
        "ontology_sha256": _sha256(ONTOLOGY_PATH),
        "draft": "resources/datasets/sparql_v2/draft.jsonl",
        "draft_sha256": _sha256(draft_path),
        "records": validation["records"],
        "families": validation["families"],
        "targets": validation["targets"],
        "merged_families": MERGE_INTO,
        "split_records": SPLIT_RECORDS,
        "target_rewrite_families": sorted(TARGET_REWRITES),
        "input_rewrite_records": sorted(INPUT_REWRITES),
        "resolved_without_row_change": sorted(RESOLVED_WITHOUT_ROW_CHANGE),
        "target_evidence": "reports/dataset_review_v2/target_evidence_v12.jsonl",
        "target_evidence_count": len(evidence),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    manifest = write_stage_b_artifacts()
    print(
        f"Stage B complete: {manifest['records']} records, "
        f"{manifest['families']} families, {manifest['targets']} targets"
    )


if __name__ == "__main__":
    main()
