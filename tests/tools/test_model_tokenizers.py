from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

from ontchatbot.catalogue import load_catalogue
from ontchatbot.research.dataset import load_release
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.research.training import MAX_TARGET_LENGTH
from ontchatbot.settings import ARTIFACTS_DIR, QUERY_CATALOGUE_PATH
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

    # BARTpho KHÔNG round-trip được ``:summaryText``: từ điển thiên về âm tiết
    # tiếng Việt không có token "summary" nên nó phát ra <unk> và chữ mất hẳn.
    # Người dùng đã quyết coi đây là **kết quả đo được của đề tài** - một model
    # chuyên tiếng Việt không biểu diễn nổi định danh của ngôn ngữ truy vấn -
    # chứ không phải lỗi phải chữa. Nên chỉ hai model kia bị ràng buộc round-trip.
    lossy = {"bartpho"}
    for name, tokenizer in tokenizers.items():
        if name in lossy:
            # ``audit_target_roundtrip`` NÉM lỗi ở đích hỏng đầu tiên, nên với
            # BARTpho phải kiểm từng đích một để chắc chắn chỗ hỏng CHỈ nằm ở
            # ``:summaryText`` - nếu nó hỏng thêm chỗ khác thì đó mới là lỗi mới.
            broken = []
            for target in targets:
                ids = tokenizer(target, add_special_tokens=False)["input_ids"]
                if tokenizer.decode(ids, skip_special_tokens=True).strip() != target.strip():
                    broken.append(target)
            assert broken, "BARTpho bỗng round-trip hết - kiểm lại, có thể đã đổi từ điển"
            assert all(":summaryText" in target for target in broken), broken[:3]
            continue
        report = audit_target_roundtrip(tokenizer, targets)
        assert len(report) == len(targets)
        assert max(row["tokens"] for row in report) <= MAX_TARGET_LENGTH
        for row in rows:
            ids = tokenizer(
                normalize_model_input(row["input"]),
                add_special_tokens=True,
            )["input_ids"]
            assert len(ids) <= 128
            if tokenizer.unk_token_id in ids:
                # Ngoại lệ DUY NHẤT được phép: chứng chỉ tiếng Nga ТРКИ viết bằng
                # bảng chữ Cyrillic, mà từ điển ViT5 (thuần tiếng Việt) không có.
                # Đây là tên thật của chứng chỉ, không đổi được. 4 câu / 6.302.
                assert re.search(r"[\u0400-\u04FF]", row["input"]), row["input"]


def test_certificate_conversion_detail_targets_fit_supported_tokenizers() -> None:
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    bartpho = _snapshot("models--vinai--bartpho-syllable", BARTPHO_REVISION)
    vit5 = ARTIFACTS_DIR / "tokenizers/vit5"
    t5gemma = _snapshot(
        "models--google--t5gemma-2-270m-270m",
        T5GEMMA_REVISION,
    )
    if not all(path.is_dir() for path in (bartpho, vit5, t5gemma)):
        pytest.skip("all three local tokenizers are required")

    spec = load_catalogue(QUERY_CATALOGUE_PATH)["certificate-criterion"]
    targets = [
        spec.target_template.replace("${certificate}", certificate)
        for certificate in spec.slots["certificate"].values
    ]
    tokenizers = {
        "bartpho": AutoTokenizer.from_pretrained(bartpho, local_files_only=True),
        "vit5": AutoTokenizer.from_pretrained(vit5, local_files_only=True),
        "t5gemma2": AutoTokenizer.from_pretrained(
            t5gemma,
            local_files_only=True,
            fix_mistral_regex=False,
        ),
    }

    for name, tokenizer in tokenizers.items():
        # BARTpho không round-trip được ``:summaryText`` - xem ghi chú ở
        # ``test_all_dataset_text_roundtrips_supported_tokenizers``.
        if name == "bartpho":
            continue
        report = audit_target_roundtrip(tokenizer, targets)
        assert max(row["tokens"] for row in report) <= MAX_TARGET_LENGTH, name


def test_compact_model_targets_fit_supported_tokenizers() -> None:
    pytest.importorskip("transformers")
    from transformers import AutoTokenizer

    bartpho = _snapshot("models--vinai--bartpho-syllable", BARTPHO_REVISION)
    vit5 = ARTIFACTS_DIR / "tokenizers/vit5"
    t5gemma = _snapshot(
        "models--google--t5gemma-2-270m-270m",
        T5GEMMA_REVISION,
    )
    if not all(path.is_dir() for path in (bartpho, vit5, t5gemma)):
        pytest.skip("all three local tokenizers are required")

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    # Bảy họ v0.4.1 trong danh sách cũ đều không còn tồn tại. Thay bằng: MỌI họ
    # trả về nhiều cột - đó chính là loại đích dài nhất, và là thứ phép kiểm này
    # muốn canh. Không chốt cứng tên họ nữa để lần refactor sau không đỏ oan.
    query_ids = sorted(
        query_id
        for query_id, spec in catalogue.items()
        if spec.tier == "primary" and spec.target_template.count("?") >= 4
    )
    assert query_ids, "không còn họ nào trả nhiều cột - phép kiểm này đang rỗng"
    fill = {"anchor": ":MajorChangeProcedure", "score": "7.5", "credits": "70",
            "rule": ":ClassSizeRule01", "program": ":Accounting", "cohort": "65",
            "amount": "520000", "certificate": ":IELTSCertificate",
            "article": "24", "clause": "3"}
    def _fill(template: str) -> str:
        for name, value in fill.items():
            template = template.replace("${" + name + "}", value)
        return template
    targets = [_fill(catalogue[query_id].target_template) for query_id in query_ids]
    language_target = catalogue["language-certificate-level"].target_template
    targets.append(
        language_target.replace("${certificate}", ":IELTSCertificate").replace(
            "${score}", "5.5"
        )
    )
    tokenizers = {
        "bartpho": AutoTokenizer.from_pretrained(bartpho, local_files_only=True),
        "vit5": AutoTokenizer.from_pretrained(vit5, local_files_only=True),
        "t5gemma2": AutoTokenizer.from_pretrained(
            t5gemma,
            local_files_only=True,
            fix_mistral_regex=False,
        ),
    }

    for name, tokenizer in tokenizers.items():
        # BARTpho không round-trip được ``:summaryText`` - xem ghi chú ở
        # ``test_all_dataset_text_roundtrips_supported_tokenizers``.
        if name == "bartpho":
            continue
        report = audit_target_roundtrip(tokenizer, targets)
        assert max(row["tokens"] for row in report) <= MAX_TARGET_LENGTH, name
