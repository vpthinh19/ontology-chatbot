"""Chấm model đã tinh chỉnh phải hỏi bằng ĐÚNG khuôn đã dạy nó.

Lượt chấm ngày 16/8 hỏi adapter bằng khuôn nhắc 12 ví dụ - khuôn dựng cho model
GỐC chưa tinh chỉnh, dài 2.253 token, không có lời hệ thống, không có khối
``<think>`` rỗng - trong khi adapter được dạy trên khuôn 61 token có đủ hai thứ
đó. Model không câm, nó chỉ trượt một token ở cùng một chỗ trong 150 trên 399
câu, và một token đó đủ để truy vấn rơi khỏi danh mục, kéo cả ba chỉ số xuống.

Không phép kiểm nào trong 327 cái bắt được, vì không cái nào so hai khuôn với
nhau. Đây là cái đó.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ontchatbot.cli.benchmark_model import fine_tuned_prompt
from ontchatbot.research.llm_lora_training import (
    MODEL_ID,
    MODEL_REVISION,
    _prompt_ids,
)
from ontchatbot.runtime.llm import FineTunedQueryGenerator, LLMQueryGenerator
from ontchatbot.runtime.text import normalize_model_input

CÂU_HỎI = (
    "thủ tục xin bảo lưu thế nào",
    "hs xet tn gom nhung gi",
    "Cho tôi hỏi đăng ký học phần khi nào ạ?",
)


def _tokenizer():
    snapshot = (
        Path.home()
        / ".cache/huggingface/hub"
        / f"models--{MODEL_ID.replace('/', '--')}"
        / "snapshots"
        / MODEL_REVISION
    )
    if not snapshot.is_dir():
        pytest.skip(f"chưa có {MODEL_ID}@{MODEL_REVISION} trong cache")
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, local_files_only=True
    )


@pytest.mark.parametrize("question", CÂU_HỎI)
def test_khuon_cham_trung_khop_khuon_huan_luyen(question: str) -> None:
    """So tới từng token, không so bằng mắt."""

    tokenizer = _tokenizer()
    huấn_luyện = _prompt_ids(tokenizer, question)
    chấm = tokenizer(
        fine_tuned_prompt(tokenizer, normalize_model_input(question)),
        add_special_tokens=False,
    )["input_ids"]

    assert chấm == huấn_luyện


def test_khuon_cham_co_loi_he_thong_va_khoi_think() -> None:
    """Hai thứ khuôn nhắc ví dụ thiếu, và thiếu cái nào cũng đủ làm lệch kết quả.

    Kiểm riêng vì phép so token ở trên sẽ đỏ khi bất kỳ chi tiết nào đổi, mà đỏ
    chung thì không nói được là đổi cái gì.
    """

    tokenizer = _tokenizer()
    prompt = fine_tuned_prompt(tokenizer, "thủ tục xin bảo lưu thế nào")

    assert "system" in prompt
    assert "<think>" in prompt
    assert "Câu hỏi:" not in prompt, "không được nhắc ví dụ cho model đã tinh chỉnh"


def test_model_da_tinh_chinh_khong_nhac_vi_du() -> None:
    """Không cần cache model: chỉ kiểm đường ống dựng prompt."""

    seen: list[str] = []

    def complete(prompt: str) -> str:
        seen.append(prompt)
        return "SELECT ?a WHERE { :A :b ?a . }"

    generator = FineTunedQueryGenerator(complete)
    generator.generate("Cho tôi hỏi đăng ký học phần khi nào ạ?")

    assert seen == [normalize_model_input("Cho tôi hỏi đăng ký học phần khi nào ạ?")]


def test_hai_duong_dung_chung_buoc_chuan_hoa_va_don_ket_qua() -> None:
    """Khác nhau ĐÚNG ở chỗ dựng prompt, không được khác chỗ nào nữa."""

    raw = "```sparql\nSELECT ?a WHERE { :A :b ?a . }\n```\n\nGiải thích thừa."
    cleaned = "SELECT ?a WHERE { :A :b ?a . }"

    tinh_chỉnh = FineTunedQueryGenerator(lambda _: raw)
    assert tinh_chỉnh.generate("câu nào cũng được") == cleaned

    assert issubclass(FineTunedQueryGenerator, LLMQueryGenerator.__bases__[0])
