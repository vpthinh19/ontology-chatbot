from __future__ import annotations

import copy
from pathlib import Path

import pytest

from ontchatbot.research.dataset import load_release
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.settings import ARTIFACTS_DIR
from ontchatbot.tools.tokenizer import (
    BARTPHO_REVISION,
    T5GEMMA_REVISION,
    VIT5_REVISION,
    VIT5_SENTINEL_MAPPING,
    VIT5_VOCAB_SIZE,
    TokenizerContractError,
    audit_target_roundtrip,
    patch_vit5_tokenizer_data,
    prepare_vit5_tokenizer,
)


def _snapshot(cache_name: str, revision: str) -> Path:
    return Path.home() / ".cache/huggingface/hub" / cache_name / "snapshots" / revision


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
    source = _snapshot("models--VietAI--vit5-base", VIT5_REVISION)
    if not source.is_dir():
        pytest.skip("ViT5 snapshot is not available locally")

    first = prepare_vit5_tokenizer(source, tmp_path / "first")
    second = prepare_vit5_tokenizer(source, tmp_path / "second")

    assert first["vocab_size"] == VIT5_VOCAB_SIZE
    assert first["source_revision"] == VIT5_REVISION
    assert first["output_sha256"] == second["output_sha256"]


def test_all_dataset_text_roundtrips_supported_tokenizers() -> None:
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    bartpho = _snapshot("models--vinai--bartpho-syllable", BARTPHO_REVISION)
    vit5 = ARTIFACTS_DIR / "tokenizers/vit5"
    t5gemma = _snapshot("models--google--t5gemma-2-270m-270m", T5GEMMA_REVISION)
    if not all(path.is_dir() for path in (bartpho, vit5, t5gemma)):
        pytest.skip("all three local tokenizers are required")

    release = load_release()
    rows = [row for split in ("train", "val", "test") for row in release[split]]
    targets = sorted({row["target"] for row in rows})
    tokenizers = {
        "bartpho": AutoTokenizer.from_pretrained(bartpho, local_files_only=True),
        "vit5": AutoTokenizer.from_pretrained(vit5, local_files_only=True),
        "t5gemma2": AutoTokenizer.from_pretrained(
            t5gemma,
            local_files_only=True,
            fix_mistral_regex=False,
        ),
    }

    for tokenizer in tokenizers.values():
        report = audit_target_roundtrip(tokenizer, targets)
        assert len(report) == 162
        assert max(row["tokens"] for row in report) <= 160
        for row in rows:
            ids = tokenizer(
                normalize_model_input(row["input"]),
                add_special_tokens=True,
            )["input_ids"]
            assert len(ids) <= 128
            assert tokenizer.unk_token_id not in ids
