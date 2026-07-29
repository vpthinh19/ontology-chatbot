from __future__ import annotations

import json
from pathlib import Path

import pytest

from ontchatbot.research.catalogue import QuerySpec
from ontchatbot.research.curation import (
    CurationError,
    assemble_staging,
    bootstrap_staging,
)


CATALOGUE = {
    "procedure-query": QuerySpec("procedure-query", "procedure", "SELECT ?answer WHERE {}", {}),
    "tuition-query": QuerySpec("tuition-query", "tuition", "SELECT ?answer WHERE {}", {}),
    "academic-rule-query": QuerySpec(
        "academic-rule-query", "academic-rule", "SELECT ?answer WHERE {}", {}
    ),
    "certificate-query": QuerySpec(
        "certificate-query", "certificate", "SELECT ?answer WHERE {}", {}
    ),
    "form-query": QuerySpec("form-query", "form", "SELECT ?answer WHERE {}", {}),
    "no-information": QuerySpec(
        "no-information", "out-of-domain", "không có thông tin", {}
    ),
}


def _row(record_id: str, query_id: str, register: str) -> dict[str, str]:
    return {
        "id": record_id,
        "query_id": query_id,
        "register": register,
        "input": f"input {record_id}",
        "target": "không có thông tin" if query_id == "no-information" else "SELECT ?answer WHERE {}",
    }


def _release() -> dict[str, list[dict[str, str]]]:
    return {
        "train": [
            _row("temporary-procedure", "procedure-query", "formal"),
            _row("temporary-ood", "no-information", "noisy"),
        ],
        "val": [
            _row("temporary-tuition", "tuition-query", "neutral"),
            _row("temporary-certificate", "certificate-query", "colloquial"),
        ],
        "test": [
            _row("temporary-academic", "academic-rule-query", "formal"),
            _row("temporary-form", "form-query", "neutral"),
        ],
    }


def _write_checklist(staging_dir: Path, checklist: dict[str, list[str]]) -> None:
    (staging_dir / "rejection_checklist.json").write_text(
        json.dumps(checklist), encoding="utf-8"
    )


def test_bootstrap_routes_six_rows_and_preserves_release_shape(tmp_path: Path) -> None:
    # A wrong domain-to-shard mapping or dropped field must fail this test.
    bootstrap_staging(_release(), CATALOGUE, tmp_path)

    expected = {
        ("procedure", "train"): ["temporary-procedure"],
        ("tuition-academic-rule", "val"): ["temporary-tuition"],
        ("tuition-academic-rule", "test"): ["temporary-academic"],
        ("certificate-form-document", "val"): ["temporary-certificate"],
        ("certificate-form-document", "test"): ["temporary-form"],
        ("out-of-domain", "train"): ["temporary-ood"],
    }
    for domain in (
        "procedure",
        "tuition-academic-rule",
        "certificate-form-document",
        "out-of-domain",
    ):
        for split in ("train", "val", "test"):
            rows = [
                json.loads(line)
                for line in (tmp_path / domain / f"{split}.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            assert [row["id"] for row in rows] == expected.get((domain, split), [])
            assert all(set(row) == {"id", "query_id", "register", "input", "target"} for row in rows)

    assert list((tmp_path / "reviews").iterdir()) == []
    assert json.loads((tmp_path / "rejection_checklist.json").read_text(encoding="utf-8")) == json.loads(
        Path("resources/cases/rejection_checklist.json").read_text(encoding="utf-8")
    )


def test_assembly_assigns_deterministic_ids_and_remaps_checklist(tmp_path: Path) -> None:
    # Reordering shards, split traversal, or checklist remapping must fail this test.
    bootstrap_staging(_release(), CATALOGUE, tmp_path)
    _write_checklist(
        tmp_path,
        {
            "greeting-social": [],
            "unrelated": [],
            "near-domain-missing": [],
            "ambiguous": [],
            "noisy-out-of-domain": [],
            "mixed": [],
            "hard-negative": ["temporary-ood"],
        },
    )

    release, checklist = assemble_staging(tmp_path)

    assert [row["id"] for row in release["train"]] == [
        "question-000001",
        "question-000002",
    ]
    assert [row["id"] for row in release["val"]] == [
        "question-000003",
        "question-000004",
    ]
    assert [row["id"] for row in release["test"]] == [
        "question-000005",
        "question-000006",
    ]
    assert checklist["hard-negative"] == ["question-000002"]
    assert release["train"][0] == {
        **_release()["train"][0],
        "id": "question-000001",
    }


def test_assembly_sorts_temporary_ids_within_a_staged_shard(tmp_path: Path) -> None:
    # Retaining the manually written JSONL order instead of temporary-ID order must fail.
    release = _release()
    release["train"].append(_row("temporary-alpha", "procedure-query", "neutral"))
    bootstrap_staging(release, CATALOGUE, tmp_path)
    _write_checklist(tmp_path, {"hard-negative": ["temporary-ood"]})

    assembled, _ = assemble_staging(tmp_path)

    assert [row["input"] for row in assembled["train"]] == [
        "input temporary-alpha",
        "input temporary-procedure",
        "input temporary-ood",
    ]


def test_assembly_rejects_duplicate_temporary_ids(tmp_path: Path) -> None:
    # Silently assigning one final ID to two staged rows must fail this test.
    release = _release()
    release["val"][0]["id"] = "temporary-procedure"
    bootstrap_staging(release, CATALOGUE, tmp_path)

    with pytest.raises(CurationError, match="duplicate temporary id: temporary-procedure"):
        assemble_staging(tmp_path)


def test_assembly_rejects_checklist_id_absent_from_ood_rows(tmp_path: Path) -> None:
    # A checklist reference outside the OOD shard must fail this test.
    bootstrap_staging(_release(), CATALOGUE, tmp_path)
    _write_checklist(tmp_path, {"hard-negative": ["missing-temporary-id"]})

    with pytest.raises(CurationError, match="checklist id is not an out-of-domain row"):
        assemble_staging(tmp_path)
