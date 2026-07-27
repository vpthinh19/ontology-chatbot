"""Apply manually reviewed Stage C language decisions to the semantic draft."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..runtime.sparql import execute_select, load_ontology
from ..runtime.text import normalize_model_input
from ..settings import PROJECT_ROOT
from .audit import _duplicate_report
from .dataset import load_dataset, validate_dataset

DATASET_DIR = PROJECT_ROOT / "resources/datasets/sparql_v2"
SOURCE_PATH = DATASET_DIR / "draft.jsonl"
TARGET_PATH = DATASET_DIR / "language_draft.jsonl"
REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
DECISIONS_PATH = REVIEW_DIR / "stage_c_decisions.json"
AUDIT_PATH = REVIEW_DIR / "stage_c_audit.json"
EVIDENCE_PATH = REVIEW_DIR / "target_evidence_stage_c.jsonl"
ONTOLOGY_PATH = PROJECT_ROOT / "resources/ontology/ontology_v12.ttl"

EXPECTED_REVIEW_GROUPS = {
    "cap-001--cap-010",
    "cap-011--cap-020",
    "cap-021--cap-030",
    "cap-031--cap-040",
    "cap-041--cap-050",
    "cap-051--cap-060",
    "cap-061--cap-074",
    "aggregate-and-filter",
}

META_LANGUAGE = re.compile(
    r"\b(?:ontology|class|cá thể|cơ sở tri thức|chatbot|mô hình hoá|mô hình hóa|đầu ra)\b"
    r"|\b(?:hệ thống|dữ liệu)\s+(?:đang|hiện|có|ghi|lưu|biết|mô tả)",
    re.IGNORECASE,
)
UNNATURAL_FILLER = re.compile(r"\b(?:ad|check|full|list)\b", re.IGNORECASE)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply_decisions() -> tuple[list[dict[str, str]], dict[str, Any]]:
    source = load_dataset(SOURCE_PATH)
    decisions = _read_json(DECISIONS_PATH)
    stage_b_manifest = _read_json(REVIEW_DIR / "completion_manifest.json")
    if _sha256(SOURCE_PATH) != stage_b_manifest["draft_sha256"]:
        raise ValueError("Stage B draft checksum changed after semantic review")
    if set(decisions["reviewed_groups"]) != EXPECTED_REVIEW_GROUPS:
        raise ValueError("Stage C has not reviewed every required group")

    rows_by_id = {row["id"]: row for row in source}
    if len(rows_by_id) != len(source) or len(source) != 948:
        raise ValueError("unexpected or duplicate Stage B record IDs")

    input_rewrites = decisions["input_rewrites"]
    register_rewrites = decisions["register_rewrites"]
    family_rewrites = decisions["family_rewrites"]
    drops = decisions["drop_records"]
    action_ids = set(input_rewrites) | set(register_rewrites) | set(family_rewrites) | set(drops)
    unknown = action_ids - set(rows_by_id)
    if unknown:
        raise ValueError(f"Stage C decisions reference unknown IDs: {sorted(unknown)}")
    if set(drops) & (set(input_rewrites) | set(register_rewrites) | set(family_rewrites)):
        raise ValueError("dropped records must not also be rewritten")

    output: list[dict[str, str]] = []
    for source_row in source:
        record_id = source_row["id"]
        if record_id in drops:
            continue
        row = dict(source_row)
        if record_id in input_rewrites:
            row["input"] = input_rewrites[record_id]
        if record_id in register_rewrites:
            row["register"] = register_rewrites[record_id]
        if record_id in family_rewrites:
            row["family_id"] = family_rewrites[record_id]
        output.append(row)

    graph = load_ontology(ONTOLOGY_PATH)
    validation = validate_dataset(output, graph)
    if validation["empty_result_ids"]:
        raise ValueError(f"empty target results: {validation['empty_result_ids']}")

    for row in output:
        if row["target"] != rows_by_id[row["id"]]["target"]:
            raise ValueError(f"Stage C changed a locked target: {row['id']}")

    return output, validation


def build_audit(rows: list[dict[str, str]], validation: dict[str, Any]) -> dict[str, Any]:
    decisions = _read_json(DECISIONS_PATH)
    family_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        family_rows[row["family_id"]].append(row)

    normalized: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        normalized[normalize_model_input(row["input"]).casefold()].append(row["id"])

    meta_ids = [row["id"] for row in rows if META_LANGUAGE.search(row["input"])]
    filler_ids = [row["id"] for row in rows if UNNATURAL_FILLER.search(row["input"])]
    duplicate_groups = [ids for ids in normalized.values() if len(ids) > 1]
    family_target_counts = {
        family: len({row["target"] for row in values})
        for family, values in family_rows.items()
    }
    duplicates = _duplicate_report(
        [dict(row, _split="stage_c") for row in rows],
        threshold=0.84,
    )

    blocking_checks = (
        meta_ids,
        filler_ids,
        duplicate_groups,
        duplicates["near"]["pairs"],
        [family for family, count in family_target_counts.items() if count != 1],
        validation["empty_result_ids"],
    )

    return {
        "stage": "C",
        "status": "language_review_complete" if not any(blocking_checks) else "review_required",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "source_sha256": _sha256(SOURCE_PATH),
        "decisions": str(DECISIONS_PATH.relative_to(PROJECT_ROOT)),
        "decisions_sha256": _sha256(DECISIONS_PATH),
        "records_before": 948,
        "records_after": len(rows),
        "records_rewritten": len(decisions["input_rewrites"]),
        "records_dropped": len(decisions["drop_records"]),
        "families_after": len(family_rows),
        "targets_after": validation["targets"],
        "register_counts": dict(sorted(Counter(row["register"] for row in rows).items())),
        "query_shape_counts": dict(sorted(Counter(row["query_shape"] for row in rows).items())),
        "family_size_counts": {
            str(size): count
            for size, count in sorted(Counter(len(value) for value in family_rows.values()).items())
        },
        "meta_language_ids": meta_ids,
        "unnatural_filler_ids": filler_ids,
        "normalized_duplicate_groups": duplicate_groups,
        "lexical_near_duplicate_threshold": duplicates["threshold"],
        "lexical_near_duplicate_pairs": duplicates["near"]["pairs"],
        "families_with_multiple_targets": sorted(
            family for family, count in family_target_counts.items() if count != 1
        ),
        "empty_result_ids": validation["empty_result_ids"],
    }


def write_stage_c_artifacts() -> dict[str, Any]:
    rows, validation = apply_decisions()
    _write_jsonl(TARGET_PATH, rows)

    graph = load_ontology(ONTOLOGY_PATH)
    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_target[row["target"]].append(row)
    evidence = []
    for target, target_rows in sorted(by_target.items()):
        result = execute_select(graph, target)
        evidence.append(
            {
                "target": target,
                "family_ids": sorted({row["family_id"] for row in target_rows}),
                "record_ids": [row["id"] for row in target_rows],
                "result_count": len(result),
                "result": result,
            }
        )
    _write_jsonl(EVIDENCE_PATH, evidence)

    audit = build_audit(rows, validation)
    audit["target"] = str(TARGET_PATH.relative_to(PROJECT_ROOT))
    audit["target_sha256"] = _sha256(TARGET_PATH)
    audit["target_evidence"] = str(EVIDENCE_PATH.relative_to(PROJECT_ROOT))
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    audit = write_stage_c_artifacts()
    print(
        f"Stage C draft: {audit['records_after']} records, "
        f"{audit['families_after']} families, {audit['targets_after']} targets; "
        f"meta={len(audit['meta_language_ids'])}, filler={len(audit['unnatural_filler_ids'])}"
    )


if __name__ == "__main__":
    main()
