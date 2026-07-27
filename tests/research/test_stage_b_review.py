import hashlib
import json
from collections import Counter
from pathlib import Path

from ontchatbot.runtime.sparql import execute_select, load_ontology
from ontchatbot.settings import PROJECT_ROOT


REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
SOURCE_WORKSHEET = PROJECT_ROOT / "reports/dataset_audit_v1/family_review.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_stage_b_has_one_reviewed_decision_per_frozen_family() -> None:
    manifest = json.loads(
        (REVIEW_DIR / "decision_manifest.json").read_text(encoding="utf-8")
    )
    source = _read_jsonl(SOURCE_WORKSHEET)
    decisions = _read_jsonl(REVIEW_DIR / "family_decisions.jsonl")

    assert hashlib.sha256(SOURCE_WORKSHEET.read_bytes()).hexdigest() == manifest[
        "source_worksheet_sha256"
    ]
    assert len(source) == len(decisions) == manifest["expected_family_count"] == 401
    assert [row["family_id"] for row in decisions] == [
        row["family_id"] for row in source
    ]
    assert all(row["review_status"] == "reviewed" for row in decisions)
    assert all(row["reviewer_notes"] for row in decisions)
    assert set(row["reviewer_decision"] for row in decisions) <= {
        "keep",
        "fix",
        "split",
        "merge",
        "drop",
    }
    assert Counter(row["reviewer_decision"] for row in decisions) == {
        "keep": 346,
        "fix": 49,
        "merge": 5,
        "split": 1,
    }
    assert Counter(row["v2_scope"] for row in decisions) == {
        "v2_candidate": 237,
        "legacy_test_audit_only": 164,
    }


def test_stage_b_selectors_match_only_the_reviewed_frozen_families() -> None:
    manifest = json.loads(
        (REVIEW_DIR / "decision_manifest.json").read_text(encoding="utf-8")
    )
    source = _read_jsonl(SOURCE_WORKSHEET)
    matches = Counter()

    for group in manifest["groups"]:
        selector = group["selector"]
        selected = [
            row
            for row in source
            if (
                "target_contains" in selector
                and selector["target_contains"] in row["target"]
            )
            or (
                "family_ids" in selector
                and row["family_id"] in selector["family_ids"]
            )
        ]
        assert len(selected) == group["expected_matches"]
        matches.update(row["family_id"] for row in selected)

    assert max(matches.values()) == 1


def test_stage_b_target_evidence_matches_ontology_v11() -> None:
    manifest = json.loads(
        (REVIEW_DIR / "decision_manifest.json").read_text(encoding="utf-8")
    )
    ontology_path = PROJECT_ROOT / manifest["ontology"]
    evidence = _read_jsonl(REVIEW_DIR / "target_evidence.jsonl")
    decisions = _read_jsonl(REVIEW_DIR / "family_decisions.jsonl")

    assert hashlib.sha256(ontology_path.read_bytes()).hexdigest() == manifest[
        "ontology_sha256"
    ]
    assert len(evidence) == len({row["target"] for row in decisions}) == 80

    graph = load_ontology(ontology_path)
    for item in evidence:
        actual = execute_select(graph, item["target"])
        assert actual == item["result"]
        assert item["result_count"] == len(actual) > 0
        assert item["family_ids"] == [
            row["family_id"]
            for row in decisions
            if row["target"] == item["target"]
        ]
