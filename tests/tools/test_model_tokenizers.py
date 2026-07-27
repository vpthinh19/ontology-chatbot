from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ontchatbot.tools.tokenizer import (
    BARTPHO_REVISION,
    TOKENIZER_TARGET_PROBES,
    VIT5_REVISION,
    VIT5_SENTINEL_MAPPING,
    VIT5_VOCAB_SIZE,
    TokenizerContractError,
    patch_vit5_tokenizer_data,
    prepare_vit5_tokenizer,
    audit_target_roundtrip,
)


def _local_vit5_snapshot() -> Path:
    return (
        Path.home()
        / ".cache/huggingface/hub/models--VietAI--vit5-base/snapshots"
        / VIT5_REVISION
    )


def test_patch_preserves_vocab_size_and_ids() -> None:
    vocab = {f"token-{index}": index for index in range(VIT5_VOCAB_SIZE)}
    for old, (_, token_id) in VIT5_SENTINEL_MAPPING.items():
        del vocab[f"token-{token_id}"]
        vocab[old] = token_id
    source = {"model": {"type": "BPE", "vocab": vocab}}

    fixed = patch_vit5_tokenizer_data(source)

    assert len(fixed["model"]["vocab"]) == VIT5_VOCAB_SIZE
    for old, (new, token_id) in VIT5_SENTINEL_MAPPING.items():
        assert old not in fixed["model"]["vocab"]
        assert fixed["model"]["vocab"][new] == token_id
    assert source != fixed


def test_patch_rejects_unexpected_source_ids() -> None:
    vocab = {f"token-{index}": index for index in range(VIT5_VOCAB_SIZE)}
    source = {"model": {"type": "BPE", "vocab": vocab}}

    with pytest.raises(TokenizerContractError, match="expected <extra_id_0>"):
        patch_vit5_tokenizer_data(copy.deepcopy(source))


def test_prepared_tokenizer_reloads_and_is_deterministic(tmp_path: Path) -> None:
    pytest.importorskip("transformers")
    source = _local_vit5_snapshot()
    if not source.is_dir():
        pytest.skip("ViT5 snapshot is not available locally")

    first = prepare_vit5_tokenizer(source, tmp_path / "first")
    second = prepare_vit5_tokenizer(source, tmp_path / "second")

    assert first["vocab_size"] == VIT5_VOCAB_SIZE
    assert first["source_revision"] == VIT5_REVISION
    assert first["output_sha256"] == second["output_sha256"]

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(tmp_path / "first", local_files_only=True)
    assert len(tokenizer) == VIT5_VOCAB_SIZE
    for _, (token, token_id) in VIT5_SENTINEL_MAPPING.items():
        assert tokenizer.convert_tokens_to_ids(token) == token_id


def test_bartpho_roundtrips_the_common_sparql_targets() -> None:
    pytest.importorskip("transformers")
    source = (
        Path.home()
        / ".cache/huggingface/hub/models--vinai--bartpho-syllable/snapshots"
        / BARTPHO_REVISION
    )
    if not source.is_dir():
        pytest.skip("BARTpho snapshot is not available locally")

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        source,
        local_files_only=True,
        trust_remote_code=True,
    )
    report = audit_target_roundtrip(tokenizer, TOKENIZER_TARGET_PROBES)
    assert len(report) == len(TOKENIZER_TARGET_PROBES)


def test_v2_targets_roundtrip_both_model_tokenizers() -> None:
    pytest.importorskip("transformers")
    project_root = Path(__file__).resolve().parents[2]
    bartpho_source = (
        Path.home()
        / ".cache/huggingface/hub/models--vinai--bartpho-syllable/snapshots"
        / BARTPHO_REVISION
    )
    vit5_source = project_root / "artifacts/tokenizers/vit5"
    evidence = project_root / "reports/dataset_review_v2/target_evidence_v12.jsonl"
    if not bartpho_source.is_dir() or not (vit5_source / "tokenizer.json").is_file():
        pytest.skip("both prepared model tokenizers are required")

    from transformers import AutoTokenizer

    targets = [
        json.loads(line)["target"]
        for line in evidence.read_text(encoding="utf-8").splitlines()
        if line
    ]
    bartpho = AutoTokenizer.from_pretrained(
        bartpho_source,
        local_files_only=True,
        trust_remote_code=True,
    )
    vit5 = AutoTokenizer.from_pretrained(vit5_source, local_files_only=True)

    bartpho_report = audit_target_roundtrip(bartpho, targets)
    vit5_report = audit_target_roundtrip(vit5, targets)

    assert len(bartpho_report) == len(vit5_report) == 87
    assert max(row["tokens"] for row in bartpho_report) == 91
    assert max(row["tokens"] for row in vit5_report) == 123


def test_stage_c_sources_and_targets_fit_both_tokenizers() -> None:
    pytest.importorskip("transformers")
    project_root = Path(__file__).resolve().parents[2]
    bartpho_source = (
        Path.home()
        / ".cache/huggingface/hub/models--vinai--bartpho-syllable/snapshots"
        / BARTPHO_REVISION
    )
    vit5_source = project_root / "artifacts/tokenizers/vit5"
    draft_path = project_root / "resources/datasets/sparql_v2/language_draft.jsonl"
    if not bartpho_source.is_dir() or not (vit5_source / "tokenizer.json").is_file():
        pytest.skip("both prepared model tokenizers are required")

    from transformers import AutoTokenizer

    from ontchatbot.research.audit_learning import tokenizer_report

    rows = [
        json.loads(line)
        for line in draft_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    release = {"train": rows, "val": [], "test": []}
    bartpho = AutoTokenizer.from_pretrained(
        bartpho_source,
        local_files_only=True,
        trust_remote_code=True,
    )
    vit5 = AutoTokenizer.from_pretrained(vit5_source, local_files_only=True)

    bartpho_report = tokenizer_report("bartpho", bartpho, release)
    vit5_report = tokenizer_report("vit5", vit5, release)

    assert bartpho_report["source_unknown_records"] == []
    assert vit5_report["source_unknown_records"] == []
    assert bartpho_report["source_over_budget_records"] == 0
    assert vit5_report["source_over_budget_records"] == 0
    assert bartpho_report["target_unknown_tokens"] == 0
    assert vit5_report["target_unknown_tokens"] == 0
    assert bartpho_report["target_roundtrip_failures"] == 0
    assert vit5_report["target_roundtrip_failures"] == 0
    assert bartpho_report["source_tokens"]["max"] == 32
    assert vit5_report["source_tokens"]["max"] == 30
    assert bartpho_report["target_tokens"]["max"] == 93
    assert vit5_report["target_tokens"]["max"] == 124


def test_stage_d_sources_and_targets_fit_both_tokenizers() -> None:
    pytest.importorskip("transformers")
    project_root = Path(__file__).resolve().parents[2]
    bartpho_source = (
        Path.home()
        / ".cache/huggingface/hub/models--vinai--bartpho-syllable/snapshots"
        / BARTPHO_REVISION
    )
    vit5_source = project_root / "artifacts/tokenizers/vit5"
    draft_path = project_root / "resources/datasets/sparql_v2/coverage_draft.jsonl"
    if not bartpho_source.is_dir() or not (vit5_source / "tokenizer.json").is_file():
        pytest.skip("both prepared model tokenizers are required")

    from transformers import AutoTokenizer

    from ontchatbot.research.audit_learning import tokenizer_report

    rows = [
        json.loads(line)
        for line in draft_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    release = {"train": rows, "val": [], "test": []}
    bartpho = AutoTokenizer.from_pretrained(
        bartpho_source,
        local_files_only=True,
        trust_remote_code=True,
    )
    vit5 = AutoTokenizer.from_pretrained(vit5_source, local_files_only=True)

    bartpho_report = tokenizer_report("bartpho", bartpho, release)
    vit5_report = tokenizer_report("vit5", vit5, release)
    for report in (bartpho_report, vit5_report):
        assert report["source_unknown_records"] == []
        assert report["source_over_budget_records"] == 0
        assert report["target_unknown_tokens"] == 0
        assert report["target_roundtrip_failures"] == 0
    assert bartpho_report["source_tokens"]["max"] == 32
    assert vit5_report["source_tokens"]["max"] == 30
    assert bartpho_report["target_tokens"]["max"] == 93
    assert vit5_report["target_tokens"]["max"] == 124
