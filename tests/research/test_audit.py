from __future__ import annotations

import copy
import json
from pathlib import Path

from ontchatbot.research.audit import (
    audit_release,
    load_validation_reports,
)
from ontchatbot.research.audit_report import render_markdown, write_audit_outputs
from ontchatbot.research.dataset import load_release
from ontchatbot.runtime.sparql import load_ontology

V1_DATASET_DIR = Path("resources/datasets/sparql_v1")


class _RoundTripTokenizer:
    unk_token_id = None

    def __len__(self) -> int:
        return 256

    def __call__(self, text: str, *, add_special_tokens: bool) -> dict[str, list[int]]:
        assert add_special_tokens is True
        return {"input_ids": [ord(character) for character in text]}

    def decode(self, ids: list[int], *, skip_special_tokens: bool) -> str:
        assert skip_special_tokens is True
        return "".join(chr(token_id) for token_id in ids)


def test_v1_audit_is_read_only_and_exposes_learning_contract() -> None:
    release = load_release(V1_DATASET_DIR)
    original = copy.deepcopy(release)
    validation_case = {
        "training": {"model": "vit5", "seed": 7},
        "cases": [{"id": release["val"][0]["id"], "answer_exact": True}],
    }

    report, worksheet = audit_release(
        release,
        load_ontology(),
        validation_reports=[validation_case],
    )

    assert release == original
    assert report["read_only"] is True
    assert report["baseline"]["records"] == 1112
    assert report["baseline"]["validation"]["ok"] is True
    assert report["distributions"]["families"]["total"] == 401
    assert len(report["learning_contract"]["targets_missing_from_train"]["val"]) == 1
    assert report["learning_contract"]["ontology_terms_missing_from_train"]["val"] == []
    assert report["duplicates"]["exact"]["pair_count"] == 0
    assert report["ontology_coverage"]["datatype_properties"]["covered"] == 13
    assert report["validation_learning_evidence"]["by_model"]["vit5"][
        "answer_exact_rate"
    ] == 1.0
    assert len(worksheet) == 401
    assert all(row["review_status"] == "pending" for row in worksheet)


def test_audit_collects_tokenizer_evidence() -> None:
    report, _ = audit_release(
        load_release(V1_DATASET_DIR),
        load_ontology(),
        tokenizers={"roundtrip": _RoundTripTokenizer()},
    )

    tokenizer = report["tokenizers"]["roundtrip"]
    assert tokenizer["target_roundtrip_failures"] == 0
    assert tokenizer["target_unknown_tokens"] == 0


def test_audit_outputs_are_reproducible_files(tmp_path) -> None:
    report, worksheet = audit_release(load_release(V1_DATASET_DIR), load_ontology())

    write_audit_outputs(tmp_path, report, worksheet)

    reloaded = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert reloaded == report
    assert (tmp_path / "report.md").read_text(encoding="utf-8") == render_markdown(report)
    assert len((tmp_path / "family_review.jsonl").read_text(encoding="utf-8").splitlines()) == 401


def test_validation_loader_never_reads_benchmark_metrics(tmp_path) -> None:
    run_dir = tmp_path / "vit5/seed-7"
    run_dir.mkdir(parents=True)
    validation = {
        "training": {"model": "vit5", "seed": 7},
        "cases": [{"id": "example", "answer_exact": True}],
    }
    (run_dir / "metrics.json").write_text(json.dumps(validation), encoding="utf-8")
    (run_dir / "benchmark_metrics.json").write_text(
        json.dumps({"cases": [{"id": "forbidden"}]}),
        encoding="utf-8",
    )

    reports = load_validation_reports(tmp_path)

    assert len(reports) == 1
    assert reports[0]["cases"][0]["id"] == "example"
