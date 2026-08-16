"""Gom lô lúc chấm phải cho ra ĐÚNG kết quả của việc hỏi từng câu.

Bộ chấm sinh từng câu một nên 788 câu val+test mất hơn ba tiếng, lâu hơn cả
lượt huấn luyện. Gom lô chữa được chỗ đó, nhưng nó mở ra một kiểu hỏng lặng lẽ:
đường gom lô và đường một câu trôi ra hai nhánh khác nhau, rồi con số báo cáo
không còn là con số của thứ chạy thật. Mấy phép kiểm dưới đây neo hai đường vào
nhau.
"""

from __future__ import annotations

import pytest

from ontchatbot.runtime.llm import Example, LLMQueryGenerator
from ontchatbot.runtime.text import normalize_model_input

EXAMPLES = (
    Example.build("thủ tục xin bảo lưu thế nào", "SELECT ?a WHERE { :A :b ?a . }"),
    Example.build("hồ sơ xét tốt nghiệp gồm gì", "SELECT ?a WHERE { :B :b ?a . }"),
    Example.build("đăng ký học phần khi nào", "SELECT ?a WHERE { :C :b ?a . }"),
)

QUESTIONS = (
    "xin bảo lưu cần giấy tờ gì",
    "đk hp lúc nào",
    "thời tiết hôm nay ra sao",
)


def _echo(prompt: str) -> str:
    """Trả lại phần đuôi prompt, để kết quả phụ thuộc vào prompt đã dựng."""

    return prompt.rsplit("Câu hỏi:", 1)[-1].strip()


def test_gom_lo_cho_ra_dung_ket_qua_hoi_tung_cau() -> None:
    seen: list[str] = []

    def batch(prompts):
        seen.extend(prompts)
        return [_echo(prompt) for prompt in prompts]

    một_câu = LLMQueryGenerator(_echo, EXAMPLES, shots=2)
    theo_lô = LLMQueryGenerator(_echo, EXAMPLES, shots=2, complete_batch=batch)

    assert theo_lô.generate_many(QUESTIONS) == [
        một_câu.generate(question) for question in QUESTIONS
    ]
    # Và model phải nhận ĐÚNG prompt của đường một câu, không phải một biến thể:
    # cùng bước chuẩn hoá, cùng ví dụ nhắc kèm, cùng thứ tự.
    assert seen == [
        một_câu.build_prompt(normalize_model_input(question))
        for question in QUESTIONS
    ]


def test_khong_co_ham_gom_lo_thi_lui_ve_hoi_tung_cau() -> None:
    """Đường phục vụ không biết gì về gom lô, và không cần phải biết."""

    generator = LLMQueryGenerator(_echo, EXAMPLES, shots=2)

    assert generator.generate_many(QUESTIONS) == [
        generator.generate(question) for question in QUESTIONS
    ]


def test_giu_nguyen_thu_tu_dua_vao() -> None:
    """Bộ chấm ghép câu hỏi với dự đoán theo VỊ TRÍ, nên lệch thứ tự là chấm sai
    toàn bộ mà không có triệu chứng nào."""

    def batch(prompts):
        return [f"#{index}" for index, _ in enumerate(prompts)]

    generator = LLMQueryGenerator(_echo, EXAMPLES, shots=2, complete_batch=batch)

    assert generator.generate_many(QUESTIONS) == ["#0", "#1", "#2"]


def test_gom_lo_tra_thieu_ket_qua_thi_bao_loi() -> None:
    """Thiếu một kết quả là mọi câu sau đó ghép lệch một ô. Phải chết ngay."""

    generator = LLMQueryGenerator(
        _echo, EXAMPLES, shots=2, complete_batch=lambda prompts: list(prompts)[:-1]
    )

    with pytest.raises(ValueError, match="gom lô trả về"):
        generator.generate_many(QUESTIONS)


def test_danh_sach_rong_khong_goi_model() -> None:
    def batch(prompts):
        raise AssertionError("không được gọi model cho danh sách rỗng")

    generator = LLMQueryGenerator(_echo, EXAMPLES, shots=2, complete_batch=batch)

    assert generator.generate_many([]) == []
