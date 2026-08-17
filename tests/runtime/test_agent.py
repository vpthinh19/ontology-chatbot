"""Canh hợp đồng giữa trợ lý và công cụ tra cứu.

Mô hình ngôn ngữ chỉ thấy hai thứ trước khi quyết định gọi công cụ: khuôn nhắc
hệ thống và mô tả công cụ. Cả hai là văn bản, nên chúng hỏng lặng lẽ - không có
ngoại lệ nào được ném ra khi một hướng dẫn biến mất, chỉ có chất lượng câu trả
lời tụt xuống mà không rõ vì sao.
"""

from __future__ import annotations

import pytest

from ontchatbot.runtime.agent import (
    TOOL_DESCRIPTION,
    OntologyVocabulary,
    build_instructions,
    build_tool,
)

pytest.importorskip("agents", reason="cần thư viện openai-agents")


class _StubChatbot:
    """Đứng thay đường tra cứu thật để phép kiểm không cần model lẫn đồ thị."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def answer(self, question: str) -> str:
        self.asked.append(question)
        return f"dữ kiện của {question}"


VOCABULARY = OntologyVocabulary(
    procedures=("Thủ tục nghỉ học tạm thời",),
    units=("Phòng Đào tạo Đại học",),
    forms=("Mục tải: Đơn xin hoãn thi",),
    programs=("Công nghệ thông tin",),
)


def test_tool_tells_the_model_to_send_keywords_not_sentences() -> None:
    """Hướng dẫn rút câu hỏi thành từ khoá phải tới được mô hình.

    Thư viện chỉ lấy câu tóm tắt và đoạn đầu của chú thích làm mô tả công cụ,
    nên phần ví dụ từng bị cắt mất mà không có dấu hiệu nào.
    """

    description = build_tool(_StubChatbot()).description

    assert "TỪ KHOÁ NGẮN" in description
    assert "Nên:" in description and "Không nên:" in description
    # Một ví dụ của mỗi phía: dạng nên gửi, và dạng câu hỏi đầy đủ nên tránh.
    assert "đăng ký học phần" in description
    assert "Hãy hướng dẫn tôi cách đăng ký học phần nhé" in description


def test_tool_passes_the_keyword_through_unchanged() -> None:
    chatbot = _StubChatbot()
    tool = build_tool(chatbot)

    assert tool.name == "tra_cuu_hoc_vu"
    assert tool.params_json_schema["required"] == ["tu_khoa"]
    assert tool.params_json_schema["properties"]["tu_khoa"]["description"]


def test_instructions_name_what_the_assistant_can_look_up() -> None:
    """Khuôn nhắc phải nêu phạm vi dữ liệu, nếu không mô hình gọi công cụ cho cả
    câu ngoài miền và trả về câu từ chối thay vì trả lời thẳng."""

    instructions = build_instructions(VOCABULARY)

    # Tên xuất hiện sau khi bỏ tiền tố phân loại của ontology: người dùng gọi
    # "nghỉ học tạm thời", không gọi "Thủ tục nghỉ học tạm thời".
    for name in (
        "nghỉ học tạm thời",
        "Phòng Đào tạo Đại học",
        "Đơn xin hoãn thi",
        "Công nghệ thông tin",
    ):
        assert name in instructions, name


def test_instructions_forbid_answering_from_memory() -> None:
    """Ranh giới của hệ thống: mô hình diễn đạt, đồ thị giữ dữ kiện."""

    instructions = build_instructions(VOCABULARY)

    assert "tra_cuu_hoc_vu" in instructions
    assert "đừng suy đoán" in instructions
    assert "đừng bịa số" in instructions
    # Quy tắc gọi công cụ phải đứng TRƯỚC danh sách chủ đề. Đảo lại thì nó bị
    # chôn giữa một khối tên dài và tỉ lệ gọi công cụ tụt hẳn.
    assert instructions.index("GỌI `tra_cuu_hoc_vu` TRƯỚC") < instructions.index("Thủ tục:")
    # Trích dẫn và đường dẫn phải đi tới câu trả lời cuối, nếu không người đọc
    # mất đường đối chiếu với văn bản gốc.
    assert "trích dẫn" in instructions and "đường dẫn" in instructions


def test_instructions_are_built_from_the_graph_not_written_by_hand() -> None:
    """Danh sách chép tay mục dần: ontology thêm một thủ tục thì khuôn nhắc vẫn
    nói cái cũ. Tên trong khuôn nhắc phải đến từ từ vựng truyền vào."""

    other = OntologyVocabulary(
        procedures=("Thủ tục chuyển trường",), units=(), forms=(), programs=()
    )

    assert "chuyển trường" in build_instructions(other)
    assert "nghỉ học tạm thời" not in build_instructions(other)


def test_tool_description_is_the_shared_constant() -> None:
    assert build_tool(_StubChatbot()).description == TOOL_DESCRIPTION.strip()
