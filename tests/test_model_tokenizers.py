from __future__ import annotations

import copy
from pathlib import Path

import pytest

from ontchatbot.model_tokenizers import (
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
