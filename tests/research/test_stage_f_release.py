from __future__ import annotations

import hashlib
import json

from ontchatbot.research.dataset import load_release
from ontchatbot.research.stage_e import CANDIDATE_MANIFEST_PATH, DATASET_DIR, MANIFEST_PATH
from ontchatbot.research.stage_f import AUDIT_PATH, build_structural_report
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import DATASET_DIR as DEFAULT_DATASET_DIR


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_f_freezes_v2_and_makes_it_the_default() -> None:
    candidate = _read_json(CANDIDATE_MANIFEST_PATH)
    frozen = _read_json(MANIFEST_PATH)
    audit = _read_json(AUDIT_PATH)

    assert DEFAULT_DATASET_DIR == DATASET_DIR
    assert candidate["status"] == "stage_e_candidate"
    assert frozen["status"] == "frozen"
    assert frozen["release_gate"]["status"] == "passed"
    assert frozen["release_gate"]["candidate_manifest_sha256"] == _sha256(
        CANDIDATE_MANIFEST_PATH
    )
    assert audit["status"] == "release_frozen"
    assert audit["frozen_manifest_sha256"] == _sha256(MANIFEST_PATH)
    assert all(audit["gate_checks"].values())


def test_stage_f_structural_gate_is_reproducible() -> None:
    audit = _read_json(AUDIT_PATH)
    actual = build_structural_report(load_release(DATASET_DIR), load_ontology())

    assert actual == audit["structural"]
    assert actual["passed"] is True
    assert all(actual["checks"].values())


def test_stage_f_locks_both_tokenizer_contracts() -> None:
    tokenizers = _read_json(AUDIT_PATH)["tokenizers"]

    assert tokenizers["passed"] is True
    assert tokenizers["limits"] == {"source": 128, "target": 160}
    assert all(
        all(checks.values()) for checks in tokenizers["checks"].values()
    )
    assert tokenizers["reports"]["bartpho"]["source_tokens"]["max"] == 32
    assert tokenizers["reports"]["bartpho"]["target_tokens"]["max"] == 93
    assert tokenizers["reports"]["vit5"]["source_tokens"]["max"] == 30
    assert tokenizers["reports"]["vit5"]["target_tokens"]["max"] == 124
    assert tokenizers["vit5_prepared_artifact"]["passed"] is True
