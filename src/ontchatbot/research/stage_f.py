"""Run the Stage F release gates and freeze SPARQL dataset v2."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rdflib import URIRef

from ..runtime.sparql import execute_select, load_ontology
from ..settings import ONTOLOGY_NS, PROJECT_ROOT
from ..tools.tokenizer import (
    BARTPHO_MODEL_ID,
    BARTPHO_REVISION,
    VIT5_MODEL_ID,
    VIT5_REVISION,
)
from .audit import _duplicate_report, _target_terms
from .audit_learning import MAX_SOURCE_LENGTH, MAX_TARGET_LENGTH, tokenizer_report
from .dataset import REQUIRED_SPLITS, load_release, validate_release
from .stage_e import CANDIDATE_MANIFEST_PATH, DATASET_DIR, MANIFEST_PATH, ONTOLOGY_PATH

REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
AUDIT_PATH = REVIEW_DIR / "stage_f_audit.json"
STAGE_D_EVIDENCE_PATH = REVIEW_DIR / "target_evidence_stage_d.jsonl"
VIT5_TOKENIZER_MANIFEST_PATH = PROJECT_ROOT / "artifacts/tokenizers/vit5/manifest.json"
NEAR_DUPLICATE_THRESHOLD = 0.84


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _known_local_terms(graph: Any) -> set[str]:
    terms = set()
    for subject, predicate, object_ in graph:
        for node in (subject, predicate, object_):
            if isinstance(node, URIRef) and str(node).startswith(ONTOLOGY_NS):
                terms.add(str(node)[len(ONTOLOGY_NS) :])
    return terms


def build_structural_report(
    release: Mapping[str, list[dict[str, str]]],
    graph: Any,
) -> dict[str, Any]:
    validation = validate_release(dict(release), graph)
    indexed = [
        dict(row, _split=split)
        for split in REQUIRED_SPLITS
        for row in release[split]
    ]
    input_unicode_issues = []
    input_whitespace_issues = []
    input_control_issues = []
    target_format_issues = []
    for row in indexed:
        source = row["input"]
        target = row["target"]
        if unicodedata.normalize("NFC", source) != source:
            input_unicode_issues.append(row["id"])
        if (
            source != source.strip()
            or re.search(r"\s{2,}", source)
            or any(character.isspace() and character != " " for character in source)
        ):
            input_whitespace_issues.append(row["id"])
        if any(unicodedata.category(character).startswith("C") for character in source):
            input_control_issues.append(row["id"])
        if (
            target != target.strip()
            or re.search(r"\s{2,}", target)
            or any(character.isspace() and character != " " for character in target)
        ):
            target_format_issues.append(row["id"])

    known_terms = _known_local_terms(graph)
    target_terms = set().union(*(_target_terms(row["target"]) for row in indexed))
    unknown_terms = sorted(target_terms - known_terms)

    targets = sorted({row["target"] for row in indexed})
    expected_evidence = {
        item["target"]: item["result"] for item in _read_jsonl(STAGE_D_EVIDENCE_PATH)
    }
    result_mismatches = []
    none_result_targets = []
    result_row_counts = {}
    for target in targets:
        result = execute_select(graph, target)
        result_row_counts[target] = len(result)
        if result != expected_evidence.get(target):
            result_mismatches.append(target)
        if any(value is None for row in result for value in row.values()):
            none_result_targets.append(target)

    duplicates = _duplicate_report(indexed, NEAR_DUPLICATE_THRESHOLD)
    cross_split_near = [pair for pair in duplicates["near"]["pairs"] if pair["cross_split"]]
    family_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in indexed:
        family_rows[row["family_id"]].append(row)
    invalid_family_registers = {
        family: sorted(row["register"] for row in rows)
        for family, rows in family_rows.items()
        if len(rows) != 4
        or {row["register"] for row in rows}
        != {"formal", "neutral", "colloquial", "noisy"}
    }
    target_shapes = {
        target: sorted({row["query_shape"] for row in indexed if row["target"] == target})
        for target in targets
    }
    inconsistent_target_shapes = {
        target: shapes for target, shapes in target_shapes.items() if len(shapes) != 1
    }
    checks = {
        "release_validator": validation["records"] == 936,
        "input_nfc": not input_unicode_issues,
        "input_whitespace": not input_whitespace_issues,
        "input_control_characters": not input_control_issues,
        "canonical_target_whitespace": not target_format_issues,
        "ontology_terms_exist": not unknown_terms,
        "target_evidence_unchanged": not result_mismatches and len(expected_evidence) == len(targets),
        "result_cells_are_bound_literals_or_aggregates": not none_result_targets,
        "normalized_cross_split_leakage": duplicates["exact"]["cross_split_pairs"] == 0,
        "near_duplicate_cross_split_leakage": not cross_split_near,
        "four_registers_per_family": not invalid_family_registers,
        "one_query_shape_per_target": not inconsistent_target_shapes,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "validation": validation,
        "unique_targets": len(targets),
        "known_target_terms": len(target_terms),
        "unknown_ontology_terms": unknown_terms,
        "input_unicode_issue_ids": input_unicode_issues,
        "input_whitespace_issue_ids": input_whitespace_issues,
        "input_control_issue_ids": input_control_issues,
        "target_format_issue_ids": target_format_issues,
        "target_evidence_mismatches": result_mismatches,
        "none_result_targets": none_result_targets,
        "result_row_count_summary": {
            "min": min(result_row_counts.values()),
            "max": max(result_row_counts.values()),
        },
        "normalized_exact_cross_split_pairs": duplicates["exact"]["cross_split_pairs"],
        "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
        "near_duplicate_cross_split_pairs": cross_split_near,
        "invalid_family_registers": invalid_family_registers,
        "inconsistent_target_shapes": inconsistent_target_shapes,
    }


def _verify_vit5_tokenizer_artifact() -> dict[str, Any]:
    manifest = _read_json(VIT5_TOKENIZER_MANIFEST_PATH)
    mismatches = []
    root = VIT5_TOKENIZER_MANIFEST_PATH.parent
    for name, expected in manifest["output_sha256"].items():
        path = root / name
        if not path.is_file() or _sha256(path) != expected:
            mismatches.append(name)
    return {
        "manifest_sha256": _sha256(VIT5_TOKENIZER_MANIFEST_PATH),
        "source_model": manifest["source_model"],
        "source_revision": manifest["source_revision"],
        "output_checksum_mismatches": mismatches,
        "passed": (
            manifest["source_model"] == VIT5_MODEL_ID
            and manifest["source_revision"] == VIT5_REVISION
            and not mismatches
        ),
    }


def build_tokenizer_report(
    release: Mapping[str, list[dict[str, str]]],
    bartpho_tokenizer: Any,
    vit5_tokenizer: Any,
) -> dict[str, Any]:
    reports = {
        "bartpho": tokenizer_report("bartpho", bartpho_tokenizer, release),
        "vit5": tokenizer_report("vit5", vit5_tokenizer, release),
    }
    checks = {}
    for name, report in reports.items():
        checks[name] = {
            "source_without_unknown": not report["source_unknown_records"],
            "source_within_budget": report["source_over_budget_records"] == 0,
            "target_without_unknown": report["target_unknown_tokens"] == 0,
            "target_within_budget": report["target_over_budget_targets"] == 0,
            "target_roundtrip_exact": report["target_roundtrip_failures"] == 0,
        }
    vit5_artifact = _verify_vit5_tokenizer_artifact()
    passed = all(all(values.values()) for values in checks.values()) and vit5_artifact["passed"]
    return {
        "passed": passed,
        "limits": {"source": MAX_SOURCE_LENGTH, "target": MAX_TARGET_LENGTH},
        "models": {
            "bartpho": {"model_id": BARTPHO_MODEL_ID, "revision": BARTPHO_REVISION},
            "vit5": {"model_id": VIT5_MODEL_ID, "revision": VIT5_REVISION},
        },
        "checks": checks,
        "reports": reports,
        "vit5_prepared_artifact": vit5_artifact,
    }


def _verify_candidate_manifest() -> dict[str, Any]:
    candidate = _read_json(CANDIDATE_MANIFEST_PATH)
    mismatches = []
    for relative, expected in candidate["sha256"].items():
        path = DATASET_DIR / relative
        if not path.is_file() or _sha256(path) != expected:
            mismatches.append(relative)
    return {
        "manifest": candidate,
        "sha256": _sha256(CANDIDATE_MANIFEST_PATH),
        "checksum_mismatches": mismatches,
        "passed": candidate.get("status") == "stage_e_candidate" and not mismatches,
    }


def freeze_release(bartpho_tokenizer: Any, vit5_tokenizer: Any) -> dict[str, Any]:
    release = load_release(DATASET_DIR)
    graph = load_ontology(ONTOLOGY_PATH)
    candidate = _verify_candidate_manifest()
    structural = build_structural_report(release, graph)
    tokenizers = build_tokenizer_report(release, bartpho_tokenizer, vit5_tokenizer)
    gate_checks = {
        "candidate_manifest": candidate["passed"],
        "structural_contract": structural["passed"],
        "tokenizer_contract": tokenizers["passed"],
    }
    if not all(gate_checks.values()):
        raise ValueError(f"Stage F release gate failed: {gate_checks}")

    frozen = dict(candidate["manifest"])
    frozen["status"] = "frozen"
    frozen["release_gate"] = {
        "stage": "F",
        "status": "passed",
        "candidate_manifest_sha256": candidate["sha256"],
        "audit": str(AUDIT_PATH.relative_to(PROJECT_ROOT)),
        "checks": gate_checks,
        "token_limits": tokenizers["limits"],
        "models": tokenizers["models"],
    }
    MANIFEST_PATH.write_text(
        json.dumps(frozen, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit = {
        "stage": "F",
        "status": "release_frozen",
        "dataset": "sparql_v2",
        "candidate_manifest": str(CANDIDATE_MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "candidate_manifest_sha256": candidate["sha256"],
        "frozen_manifest": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "frozen_manifest_sha256": _sha256(MANIFEST_PATH),
        "gate_checks": gate_checks,
        "candidate_checksum_mismatches": candidate["checksum_mismatches"],
        "structural": structural,
        "tokenizers": tokenizers,
        "distribution_review": {
            "status": "explained",
            "evidence": "reports/dataset_review_v2/stage_d_report.md and stage_e_report.md",
            "note": "Every split contains all five query shapes; sparse aggregate shapes are intentional and reviewed.",
        },
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit
