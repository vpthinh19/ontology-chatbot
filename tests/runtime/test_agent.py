"""Canh hợp đồng giữa trợ lý và công cụ tra cứu.

Mô hình ngôn ngữ chỉ thấy hai thứ trước khi quyết định gọi công cụ: khuôn nhắc
hệ thống và mô tả công cụ. Cả hai là văn bản, nên chúng hỏng lặng lẽ - không có
ngoại lệ nào được ném ra khi một hướng dẫn biến mất, chỉ có chất lượng câu trả
lời tụt xuống mà không rõ vì sao.
"""

from __future__ import annotations

import asyncio
import json
import pytest

from ontchatbot.runtime.agent import (
    MAX_KEYWORD_CHARACTERS,
    TOOL_DESCRIPTION,
    TOOL_SCHEMA,
    OntologyVocabulary,
    build_instructions,
    look_up_async,
)


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

    description = TOOL_SCHEMA["function"]["description"]

    assert "TỪ KHOÁ NGẮN" in description
    assert "Nên:" in description and "Không nên:" in description
    # Một ví dụ của mỗi phía: dạng nên gửi, và dạng câu hỏi đầy đủ nên tránh.
    assert "đăng ký học phần" in description
    assert "Hãy hướng dẫn tôi cách đăng ký học phần nhé" in description


def test_tool_passes_the_keyword_through_unchanged() -> None:
    function = TOOL_SCHEMA["function"]
    parameters = function["parameters"]

    assert function["name"] == "lookup_academic_information"
    assert parameters["required"] == ["keywords"]
    assert parameters["properties"]["keywords"]["description"]


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

    assert "lookup_academic_information" in instructions
    assert "đừng suy đoán" in instructions
    assert "đừng bịa số" in instructions
    # Quy tắc gọi công cụ phải đứng TRƯỚC danh sách chủ đề. Đảo lại thì nó bị
    # chôn giữa một khối tên dài và tỉ lệ gọi công cụ tụt hẳn.
    assert instructions.index("GỌI `lookup_academic_information` TRƯỚC") < (
        instructions.index("Thủ tục:")
    )
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
    assert TOOL_SCHEMA["function"]["description"] == TOOL_DESCRIPTION


def test_tool_teaches_the_model_to_read_the_structured_result_and_stop() -> None:
    description = TOOL_SCHEMA["function"]["description"]

    assert "JSON" in description
    assert "du_lieu" in description and "nguon" in description
    # Cách gọi nhiều từ khoá một lượt phải nằm trong mô tả, nếu không mô hình
    # gửi từng cụm một và mất đúng phần lợi của việc đổi sang danh sách.
    assert "DANH SÁCH" in description
    assert "tu_khoa_khong_thay" in description
    assert "không xuất hiện" in description
    assert "ĐỪNG gọi lại" in description
    assert "tu_khoa_da_cat" in description


def test_instructions_require_one_lookup_for_every_topic() -> None:
    instructions = build_instructions(VOCABULARY)

    assert "Câu hỏi có nhiều chủ đề độc lập" in instructions
    assert "đúng một lần cho từng chủ đề" in instructions
    assert "Không suy" in instructions and "luận" in instructions
    assert "bảng chung cho một ngành cụ thể" in instructions


def test_system_prompt_stays_below_four_hundred_words() -> None:
    assert len(build_instructions().split()) < 400


def test_async_tool_bounds_keywords_before_shared_lookup() -> None:
    """The shared coordinator only receives normalized, bounded keywords."""

    seen = []

    async def lookup(keywords):
        seen.append(keywords)
        return json.dumps({"trang_thai": "co_du_lieu", "du_lieu": keywords})

    result = asyncio.run(
        look_up_async(
            lookup,
            ["học phí", "học phí", "x" * (MAX_KEYWORD_CHARACTERS + 1)],
        )
    )

    payload = json.loads(result)
    assert seen == [["học phí", "x" * MAX_KEYWORD_CHARACTERS]]
    assert payload["tu_khoa_da_cat"]["so_luong_rut_gon"] == 1


def test_async_tool_keeps_domain_errors_as_no_information() -> None:
    """A failing cached lookup remains a model-readable result, not a tool error."""

    from ontchatbot.runtime.generator import QueryGenerationError
    from ontchatbot.runtime.render import NO_INFORMATION_REPLY
    from ontchatbot.runtime.sparql import SparqlError

    for error in (QueryGenerationError("rỗng"), SparqlError("sai cú pháp")):
        async def fail(_keywords, error=error):
            raise error

        assert asyncio.run(look_up_async(fail, ["học phí"])) == NO_INFORMATION_REPLY

    async def unexpected(_keywords):
        raise RuntimeError("mất kết nối")

    with pytest.raises(RuntimeError, match="mất kết nối"):
        asyncio.run(look_up_async(unexpected, ["học phí"]))
