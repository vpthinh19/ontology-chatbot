"""Apply reviewed Stage D coverage additions to the language draft."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rdflib import RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS

from ..runtime.sparql import execute_select, load_ontology
from ..runtime.text import normalize_model_input
from ..settings import ONTOLOGY_NS, PROJECT_ROOT
from .audit import _duplicate_report, _ontology_report, _target_terms
from .dataset import load_dataset, validate_dataset
from .stage_c import META_LANGUAGE, UNNATURAL_FILLER

DATASET_DIR = PROJECT_ROOT / "resources/datasets/sparql_v2"
SOURCE_PATH = DATASET_DIR / "language_draft.jsonl"
TARGET_PATH = DATASET_DIR / "coverage_draft.jsonl"
REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
DECISIONS_PATH = REVIEW_DIR / "stage_d_decisions.json"
COVERAGE_PATH = REVIEW_DIR / "stage_d_coverage.json"
AUDIT_PATH = REVIEW_DIR / "stage_d_audit.json"
EVIDENCE_PATH = REVIEW_DIR / "target_evidence_stage_d.jsonl"
ONTOLOGY_PATH = PROJECT_ROOT / "resources/ontology/ontology_v12.ttl"

EXPECTED_COMPLETED_FAMILY = "cap-066-f04"
EXPECTED_CANDIDATE_STATUSES = {"add", "complete", "defer", "not_gap"}


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


def build_coverage(rows: list[dict[str, str]], graph: Any) -> dict[str, Any]:
    """Build a factual matrix; uncovered terms remain review hints, not decisions."""

    families: dict[str, list[dict[str, str]]] = defaultdict(list)
    targets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        families[row["family_id"]].append(row)
        targets[row["target"]].append(row)

    ontology = _ontology_report({"train": rows, "val": [], "test": []}, graph)
    property_support: dict[str, dict[str, Any]] = {}
    properties = sorted(
        {
            str(subject)[len(ONTOLOGY_NS) :]
            for kind in (OWL.ObjectProperty, OWL.DatatypeProperty)
            for subject in graph.subjects(RDF.type, kind)
            if isinstance(subject, URIRef) and str(subject).startswith(ONTOLOGY_NS)
        }
    )
    for term in properties:
        family_ids = sorted(
            family
            for family, values in families.items()
            if term in _target_terms(values[0]["target"])
        )
        property_support[term] = {
            "families": len(family_ids),
            "records": sum(len(families[family]) for family in family_ids),
        }

    fact_support = []
    ignored = {RDF.type, RDFS.label, SKOS.altLabel}
    individuals = sorted(
        {
            subject
            for subject in graph.subjects(RDF.type, OWL.NamedIndividual)
            if isinstance(subject, URIRef) and str(subject).startswith(ONTOLOGY_NS)
        },
        key=str,
    )
    for subject in individuals:
        subject_term = str(subject)[len(ONTOLOGY_NS) :]
        label = next((str(value) for value in graph.objects(subject, RDFS.label)), "")
        for predicate in sorted(set(graph.predicates(subject)), key=str):
            if predicate in ignored or not str(predicate).startswith(ONTOLOGY_NS):
                continue
            predicate_term = str(predicate)[len(ONTOLOGY_NS) :]
            family_ids = sorted(
                family
                for family, values in families.items()
                if {subject_term, predicate_term} <= _target_terms(values[0]["target"])
            )
            fact_support.append(
                {
                    "subject": subject_term,
                    "label": label,
                    "predicate": predicate_term,
                    "direct_anchor_families": len(family_ids),
                }
            )

    family_shape_counts = Counter(values[0]["query_shape"] for values in families.values())
    target_family_counts = Counter()
    for target, values in targets.items():
        target_family_counts[len({row["family_id"] for row in values})] += 1

    return {
        "records": len(rows),
        "families": len(families),
        "targets": len(targets),
        "register_counts": dict(sorted(Counter(row["register"] for row in rows).items())),
        "query_shape_records": dict(sorted(Counter(row["query_shape"] for row in rows).items())),
        "query_shape_families": dict(sorted(family_shape_counts.items())),
        "family_size_histogram": {
            str(size): count
            for size, count in sorted(Counter(len(values) for values in families.values()).items())
        },
        "target_family_support_histogram": {
            str(size): count for size, count in sorted(target_family_counts.items())
        },
        "ontology_term_coverage": ontology,
        "property_support": property_support,
        "named_individual_fact_support": fact_support,
        "interpretation": [
            "Term coverage only says that an IRI occurs in a target; it is not user-need coverage.",
            "Direct-anchor fact support intentionally undercounts generic graph paths.",
            "Coverage additions are selected by the reviewed candidate decisions, not by zero-filling this matrix.",
        ],
    }


def apply_decisions() -> tuple[list[dict[str, str]], dict[str, Any]]:
    source = load_dataset(SOURCE_PATH)
    decisions = _read_json(DECISIONS_PATH)
    stage_c_audit = _read_json(REVIEW_DIR / "stage_c_audit.json")
    if _sha256(SOURCE_PATH) != stage_c_audit["target_sha256"]:
        raise ValueError("Stage C language draft checksum changed after review")

    candidates = decisions.get("candidates")
    additions = decisions.get("additions")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Stage D requires reviewed coverage candidates")
    if not isinstance(additions, list) or not additions:
        raise ValueError("Stage D requires reviewed additions")
    statuses = {item.get("status") for item in candidates}
    if not statuses <= EXPECTED_CANDIDATE_STATUSES or not {"add", "complete", "not_gap"} <= statuses:
        raise ValueError(f"invalid or incomplete candidate statuses: {sorted(statuses)}")
    if any(not item.get("reason") for item in candidates):
        raise ValueError("every coverage candidate needs a review reason")

    source_ids = {row["id"] for row in source}
    addition_ids = [row.get("id") for row in additions]
    if len(addition_ids) != len(set(addition_ids)) or source_ids & set(addition_ids):
        raise ValueError("Stage D addition IDs must be unique and new")

    existing_families = {row["family_id"] for row in source}
    reused = {row["family_id"] for row in additions} & existing_families
    if reused != {EXPECTED_COMPLETED_FAMILY}:
        raise ValueError(f"only {EXPECTED_COMPLETED_FAMILY} may be completed, got {sorted(reused)}")

    output = source + [dict(row) for row in additions]
    graph = load_ontology(ONTOLOGY_PATH)
    validation = validate_dataset(output, graph)
    if validation["empty_result_ids"]:
        raise ValueError(f"empty target results: {validation['empty_result_ids']}")

    families: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in output:
        families[row["family_id"]].append(row)
    incomplete = {
        family: sorted(row["register"] for row in values)
        for family, values in families.items()
        if len(values) != 4
        or {row["register"] for row in values} != {"formal", "neutral", "colloquial", "noisy"}
    }
    if incomplete:
        raise ValueError(f"families without four registers: {incomplete}")

    new_families = {row["family_id"] for row in additions} - existing_families
    for family in new_families:
        values = families[family]
        if len({row["target"] for row in values}) != 1 or len({row["query_shape"] for row in values}) != 1:
            raise ValueError(f"new family is not semantically consistent: {family}")
    return output, validation


def build_audit(rows: list[dict[str, str]], validation: dict[str, Any]) -> dict[str, Any]:
    decisions = _read_json(DECISIONS_PATH)
    source = load_dataset(SOURCE_PATH)
    source_ids = {row["id"] for row in source}
    added = [row for row in rows if row["id"] not in source_ids]
    normalized: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        normalized[normalize_model_input(row["input"]).casefold()].append(row["id"])
    duplicate_groups = [ids for ids in normalized.values() if len(ids) > 1]
    duplicates = _duplicate_report([dict(row, _split="stage_d") for row in rows], 0.84)
    meta_ids = [row["id"] for row in added if META_LANGUAGE.search(row["input"])]
    filler_ids = [row["id"] for row in added if UNNATURAL_FILLER.search(row["input"])]
    blockers = (
        duplicate_groups,
        duplicates["near"]["pairs"],
        meta_ids,
        filler_ids,
        validation["empty_result_ids"],
    )
    return {
        "stage": "D",
        "status": "coverage_review_complete" if not any(blockers) else "review_required",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "source_sha256": _sha256(SOURCE_PATH),
        "target": str(TARGET_PATH.relative_to(PROJECT_ROOT)),
        "records_before": len(source),
        "records_after": len(rows),
        "records_added": len(added),
        "families_before": len({row["family_id"] for row in source}),
        "families_after": validation["families"],
        "families_added": len({row["family_id"] for row in added} - {row["family_id"] for row in source}),
        "families_completed": [EXPECTED_COMPLETED_FAMILY],
        "targets_before": len({row["target"] for row in source}),
        "targets_after": validation["targets"],
        "register_counts": validation["register_counts"],
        "query_shape_counts": validation["query_shape_counts"],
        "candidate_status_counts": dict(sorted(Counter(item["status"] for item in decisions["candidates"]).items())),
        "normalized_duplicate_groups": duplicate_groups,
        "lexical_near_duplicate_threshold": duplicates["threshold"],
        "lexical_near_duplicate_pairs": duplicates["near"]["pairs"],
        "meta_language_ids": meta_ids,
        "unnatural_filler_ids": filler_ids,
        "empty_result_ids": validation["empty_result_ids"],
    }


def write_stage_d_artifacts() -> dict[str, Any]:
    rows, validation = apply_decisions()
    _write_jsonl(TARGET_PATH, rows)
    graph = load_ontology(ONTOLOGY_PATH)

    coverage = {
        "stage": "D",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "target": str(TARGET_PATH.relative_to(PROJECT_ROOT)),
        "before": build_coverage(load_dataset(SOURCE_PATH), graph),
        "after": build_coverage(rows, graph),
        "reviewed_candidates": _read_json(DECISIONS_PATH)["candidates"],
    }
    COVERAGE_PATH.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
    audit["target_sha256"] = _sha256(TARGET_PATH)
    audit["decisions_sha256"] = _sha256(DECISIONS_PATH)
    audit["coverage_sha256"] = _sha256(COVERAGE_PATH)
    audit["target_evidence"] = str(EVIDENCE_PATH.relative_to(PROJECT_ROOT))
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    audit = write_stage_d_artifacts()
    print(
        f"Stage D draft: {audit['records_after']} records, "
        f"{audit['families_after']} families, {audit['targets_after']} targets; "
        f"added={audit['records_added']}, status={audit['status']}"
    )


if __name__ == "__main__":
    main()
