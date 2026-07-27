import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ontchatbot.research.dataset import load_dataset, validate_dataset
from ontchatbot.research.stage_d import (
    AUDIT_PATH,
    COVERAGE_PATH,
    DECISIONS_PATH,
    EVIDENCE_PATH,
    SOURCE_PATH,
    TARGET_PATH,
    apply_decisions,
    build_audit,
    build_coverage,
)
from ontchatbot.runtime.sparql import execute_select, load_ontology
from ontchatbot.settings import PROJECT_ROOT


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_d_decisions_are_reviewed_and_bounded() -> None:
    decisions = _read_json(DECISIONS_PATH)
    candidates = decisions["candidates"]
    additions = decisions["additions"]

    assert {item["status"] for item in candidates} == {"add", "complete", "defer", "not_gap"}
    assert all(item["reason"] for item in candidates)
    assert len(additions) == 71
    assert len({row["id"] for row in additions}) == 71
    assert Counter(row["register"] for row in additions) == {
        "formal": 18,
        "neutral": 17,
        "colloquial": 18,
        "noisy": 18,
    }


def test_coverage_draft_is_reproducible_and_executable() -> None:
    expected, validation = apply_decisions()
    actual = load_dataset(TARGET_PATH)
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")

    assert actual == expected
    assert len(actual) == validation["records"] == 936
    assert validation["families"] == 234
    assert validation["targets"] == 102
    assert validation["empty_result_ids"] == []
    assert validate_dataset(actual, graph)["empty_result_ids"] == []


def test_stage_d_only_appends_reviewed_records() -> None:
    source = load_dataset(SOURCE_PATH)
    output = load_dataset(TARGET_PATH)
    additions = _read_json(DECISIONS_PATH)["additions"]

    assert output[: len(source)] == source
    assert output[len(source) :] == additions
    assert _read_json(AUDIT_PATH)["source_sha256"] == _sha256(SOURCE_PATH)


def test_every_stage_d_family_has_four_registers() -> None:
    families: dict[str, list[dict]] = defaultdict(list)
    for row in load_dataset(TARGET_PATH):
        families[row["family_id"]].append(row)

    assert Counter(len(rows) for rows in families.values()) == {4: 234}
    for rows in families.values():
        assert {row["register"] for row in rows} == {
            "formal",
            "neutral",
            "colloquial",
            "noisy",
        }
        assert len({row["target"] for row in rows}) == 1


def test_stage_d_audit_and_coverage_have_no_blockers() -> None:
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")
    rows = load_dataset(TARGET_PATH)
    validation = validate_dataset(rows, graph)
    expected_audit = build_audit(rows, validation)
    actual_audit = _read_json(AUDIT_PATH)
    coverage = _read_json(COVERAGE_PATH)

    for key, value in expected_audit.items():
        assert actual_audit[key] == value
    assert actual_audit["status"] == "coverage_review_complete"
    assert actual_audit["normalized_duplicate_groups"] == []
    assert actual_audit["lexical_near_duplicate_pairs"] == []
    assert actual_audit["meta_language_ids"] == []
    assert actual_audit["unnatural_filler_ids"] == []
    assert actual_audit["empty_result_ids"] == []
    assert actual_audit["target_sha256"] == _sha256(TARGET_PATH)
    assert coverage["before"] == build_coverage(load_dataset(SOURCE_PATH), graph)
    assert coverage["after"] == build_coverage(rows, graph)
    assert coverage["before"]["family_size_histogram"] == {"1": 1, "4": 216}
    assert coverage["after"]["family_size_histogram"] == {"4": 234}


def test_stage_d_target_evidence_matches_v12() -> None:
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")
    rows = load_dataset(TARGET_PATH)
    evidence = _read_jsonl(EVIDENCE_PATH)

    assert len(evidence) == len({row["target"] for row in rows}) == 102
    for item in evidence:
        assert execute_select(graph, item["target"]) == item["result"]
        assert item["result_count"] == len(item["result"]) > 0
        assert item["record_ids"] == [
            row["id"] for row in rows if row["target"] == item["target"]
        ]
