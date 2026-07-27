import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ontchatbot.research.dataset import load_dataset, validate_dataset
from ontchatbot.research.stage_c import (
    AUDIT_PATH,
    DECISIONS_PATH,
    EVIDENCE_PATH,
    EXPECTED_REVIEW_GROUPS,
    SOURCE_PATH,
    TARGET_PATH,
    apply_decisions,
    build_audit,
)
from ontchatbot.runtime.sparql import execute_select, load_ontology
from ontchatbot.settings import PROJECT_ROOT


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_c_reviewed_every_group_and_preserved_stage_b() -> None:
    decisions = _read_json(DECISIONS_PATH)
    stage_b_manifest = _read_json(PROJECT_ROOT / "reports/dataset_review_v2/completion_manifest.json")

    assert set(decisions["reviewed_groups"]) == EXPECTED_REVIEW_GROUPS
    assert _sha256(SOURCE_PATH) == stage_b_manifest["draft_sha256"]
    assert len(decisions["input_rewrites"]) == 87
    assert len(decisions["drop_records"]) == 83
    assert decisions["register_rewrites"] == {}
    assert decisions["family_rewrites"] == {"prod-0866": "cap-066-f01"}


def test_language_draft_is_reproducible_and_executable() -> None:
    expected, validation = apply_decisions()
    actual = load_dataset(TARGET_PATH)
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")

    assert actual == expected
    assert len(actual) == validation["records"] == 865
    assert validation["families"] == 217
    assert validation["targets"] == 85
    assert validate_dataset(actual, graph)["empty_result_ids"] == []


def test_stage_c_audit_has_no_language_blockers() -> None:
    rows = load_dataset(TARGET_PATH)
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")
    validation = validate_dataset(rows, graph)
    expected = build_audit(rows, validation)
    actual = _read_json(AUDIT_PATH)

    for key, value in expected.items():
        assert actual[key] == value
    assert actual["status"] == "language_review_complete"
    assert actual["meta_language_ids"] == []
    assert actual["unnatural_filler_ids"] == []
    assert actual["normalized_duplicate_groups"] == []
    assert actual["lexical_near_duplicate_pairs"] == []
    assert actual["families_with_multiple_targets"] == []
    assert actual["empty_result_ids"] == []
    assert actual["target_sha256"] == _sha256(TARGET_PATH)
    assert actual["target_evidence"] == str(EVIDENCE_PATH.relative_to(PROJECT_ROOT))


def test_every_regular_family_has_four_distinct_registers() -> None:
    families: dict[str, list[dict]] = defaultdict(list)
    for row in load_dataset(TARGET_PATH):
        families[row["family_id"]].append(row)

    sizes = Counter(len(rows) for rows in families.values())
    assert sizes == {4: 216, 1: 1}
    for family, rows in families.items():
        if family == "cap-066-f04":
            assert [row["register"] for row in rows] == ["neutral"]
        else:
            assert {row["register"] for row in rows} == {
                "formal",
                "neutral",
                "colloquial",
                "noisy",
            }


def test_stage_c_only_changes_approved_language_metadata_or_presence() -> None:
    source = {row["id"]: row for row in load_dataset(SOURCE_PATH)}
    output = {row["id"]: row for row in load_dataset(TARGET_PATH)}
    decisions = _read_json(DECISIONS_PATH)

    assert set(source) - set(output) == set(decisions["drop_records"])
    for record_id, row in output.items():
        old = source[record_id]
        assert row["id"] == old["id"]
        assert row["target"] == old["target"]
        assert row["query_shape"] == old["query_shape"]
        assert row["input"] == decisions["input_rewrites"].get(record_id, old["input"])
        assert row["register"] == decisions["register_rewrites"].get(
            record_id, old["register"]
        )
        assert row["family_id"] == decisions["family_rewrites"].get(
            record_id, old["family_id"]
        )


def test_stage_c_target_evidence_matches_v12() -> None:
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")
    rows = load_dataset(TARGET_PATH)
    evidence = _read_jsonl(EVIDENCE_PATH)

    assert len(evidence) == len({row["target"] for row in rows}) == 85
    for item in evidence:
        assert execute_select(graph, item["target"]) == item["result"]
        assert item["result_count"] == len(item["result"]) > 0
        assert item["record_ids"] == [
            row["id"] for row in rows if row["target"] == item["target"]
        ]
