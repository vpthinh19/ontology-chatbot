from __future__ import annotations

import hashlib
import json

import pytest

from ontchatbot.research.stage_e import MANIFEST_PATH, ONTOLOGY_PATH
from ontchatbot.research.stage_g import (
    AUDIT_PATH,
    PROTOCOL_PATH,
    REPORT_PATH,
    _evaluation_evidence,
)


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_g_is_locked_and_complete() -> None:
    protocol = _read_json(PROTOCOL_PATH)
    audit = _read_json(AUDIT_PATH)

    assert protocol["status"] == "complete_test_evaluated_once"
    assert protocol["test_policy"] == {
        "open_after_all_checkpoints_are_frozen": True,
        "evaluate_each_model_seed_once": True,
        "do_not_tune_after_test": True,
    }
    assert protocol["models"] == ["bartpho", "vit5", "t5gemma2"]
    assert protocol["seeds"] == [42]
    assert len(protocol["frozen_checkpoints"]) == 3
    assert audit["status"] == "complete_test_evaluated_once"
    assert audit["dataset_manifest_sha256"] == _sha256(MANIFEST_PATH)
    assert audit["ontology_sha256"] == _sha256(ONTOLOGY_PATH)
    assert REPORT_PATH.is_file()


def test_stage_g_official_result_and_conclusion_are_preserved() -> None:
    audit = _read_json(AUDIT_PATH)

    assert audit["learning_audit"]["bartpho"]["answer_exact_rate"] == 1.0
    assert audit["learning_audit"]["vit5"]["answer_exact_rate"] == 1.0
    assert audit["official"]["models"]["bartpho"]["benchmark"][
        "answer_exact_rate"
    ]["mean"] == pytest.approx(0.7)
    assert audit["official"]["models"]["vit5"]["benchmark"][
        "answer_exact_rate"
    ]["mean"] == pytest.approx(0.6357142857)
    assert audit["official"]["models"]["t5gemma2"]["benchmark"][
        "answer_exact_rate"
    ]["mean"] == pytest.approx(0.7785714286)
    assert audit["generalization"]["unseen_exact_target_records"] == 20
    assert audit["generalization"]["persistent_failures_across_all_official_runs"][
        "count"
    ] == 16
    assert audit["conclusion"]["semantic_generalization_is_solved"] is False


def test_target_novelty_is_computed_from_train_not_metadata() -> None:
    release = {
        "train": [{"target": "SEEN"}],
        "val": [],
        "test": [
            {
                "id": "seen",
                "family_id": "regular",
                "register": "neutral",
                "query_shape": "direct",
                "input": "đã thấy",
                "target": "SEEN",
            },
            {
                "id": "new",
                "family_id": "holdout",
                "register": "noisy",
                "query_shape": "aggregate",
                "input": "chưa thấy",
                "target": "NEW",
            },
        ],
    }
    cases = [
        {"id": "seen", "answer_exact": True},
        {"id": "new", "answer_exact": False},
    ]
    reports = {
        model: [{"cases": cases} for _ in range(3)]
        for model in ("bartpho", "vit5")
    }

    result = _evaluation_evidence(release, reports, {"holdout"})

    assert result["by_model"]["bartpho"]["by_target_novelty"][
        "seen_exact_target"
    ]["mean_answer_exact_rate"] == 1.0
    assert result["by_model"]["bartpho"]["by_target_novelty"][
        "unseen_exact_target"
    ]["mean_answer_exact_rate"] == 0.0
    assert result["persistent_failures_across_all_official_runs"]["count"] == 1
