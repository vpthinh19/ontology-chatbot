import hashlib
import json
from pathlib import Path

from ontchatbot.research.dataset import REQUIRED_FIELDS, load_dataset, validate_dataset
from ontchatbot.research.stage_b import build_draft
from ontchatbot.runtime.sparql import execute_select, load_ontology
from ontchatbot.settings import PROJECT_ROOT

REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
DRAFT_PATH = PROJECT_ROOT / "resources/datasets/sparql_v2/draft.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_b_completion_is_locked_to_sources_and_v12() -> None:
    manifest = json.loads(
        (REVIEW_DIR / "completion_manifest.json").read_text(encoding="utf-8")
    )

    assert manifest["stage"] == "B"
    assert manifest["status"] == "complete"
    assert manifest["records"] == 948
    assert manifest["families"] == 233
    assert manifest["targets"] == manifest["target_evidence_count"] == 87
    assert _sha256(PROJECT_ROOT / manifest["ontology"]) == manifest["ontology_sha256"]
    assert _sha256(DRAFT_PATH) == manifest["draft_sha256"]
    for name, expected in manifest["source_files"].items():
        assert _sha256(PROJECT_ROOT / "resources/datasets/sparql_v1" / name) == expected


def test_draft_is_reproducible_and_executable() -> None:
    expected, validation, expected_evidence = build_draft()
    actual = load_dataset(DRAFT_PATH)
    ontology = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")

    assert actual == expected
    assert validation["records"] == 948
    assert validate_dataset(actual, ontology)["empty_result_ids"] == []
    assert _read_jsonl(REVIEW_DIR / "target_evidence_v12.jsonl") == expected_evidence


def test_v2_draft_has_no_legacy_test_records_or_split_field() -> None:
    draft = load_dataset(DRAFT_PATH)
    legacy_test_ids = {
        row["id"]
        for row in load_dataset(PROJECT_ROOT / "resources/datasets/sparql_v1/test.jsonl")
    }

    assert all(set(row) == REQUIRED_FIELDS for row in draft)
    assert not ({row["id"] for row in draft} & legacy_test_ids)


def test_merge_split_and_role_decisions_are_applied() -> None:
    rows = {row["id"]: row for row in load_dataset(DRAFT_PATH)}
    family_ids = {row["family_id"] for row in rows.values()}

    assert not family_ids & {
        "cap-036-f02",
        "cap-049-f02",
        "cap-052-f02",
        "cap-058-f02",
        "cap-046-f03",
    }
    assert rows["prod-0262"]["family_id"] == "cap-066-f04"
    assert rows["prod-0262"]["query_shape"] == "aggregate"
    assert "COUNT" in rows["prod-0262"]["target"]
    assert rows["prod-0594"]["target"].count(":receivedBy") == 1
    assert "tiếp nhận" in rows["prod-0594"]["input"]


def test_rewritten_targets_return_the_intended_values() -> None:
    rows = {row["id"]: row for row in load_dataset(DRAFT_PATH)}
    graph = load_ontology(PROJECT_ROOT / "resources/ontology/ontology_v12.ttl")

    leave_reasons = execute_select(graph, rows["prod-0429"]["target"])
    assert len(leave_reasons) == 3
    assert all("ốm" not in row["answer"] for row in leave_reasons)

    resumption_forms = execute_select(graph, rows["prod-0437"]["target"])
    assert resumption_forms == [{"answer": "Đơn xin học trở lại"}]

    other_programs = execute_select(graph, rows["prod-0797"]["target"])
    assert len(other_programs) == 4
    assert all(row["answer"] != "Ô tô" for row in other_programs)

    receiving_phone = execute_select(graph, rows["prod-0594"]["target"])
    processing_phone = execute_select(graph, rows["prod-0597"]["target"])
    assert receiving_phone == [{"answer": "02582221900"}]
    assert processing_phone == [{"answer": "02583831148"}]
