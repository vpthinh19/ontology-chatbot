"""Canh hợp đồng giữa trợ lý và công cụ tra cứu.

Mô hình ngôn ngữ chỉ thấy hai thứ trước khi quyết định gọi công cụ: khuôn nhắc
hệ thống và mô tả công cụ. Cả hai là văn bản, nên chúng hỏng lặng lẽ - không có
ngoại lệ nào được ném ra khi một hướng dẫn biến mất, chỉ có chất lượng câu trả
lời tụt xuống mà không rõ vì sao.
"""

from __future__ import annotations

from pathlib import Path

from ontchatbot.runtime.agent import (
    TOOL_DESCRIPTION,
    TOOL_SCHEMA,
    OntologyVocabulary,
    build_instructions,
    read_vocabulary,
)
from ontchatbot.runtime.lookup import MAX_KEYWORD_CHARACTERS, MAX_KEYWORDS_PER_LOOKUP
from ontchatbot.search import Ontology, TurtleFileSource

MINI_ONTOLOGY = Path(__file__).resolve().parents[1] / "fixtures" / "mini-ontology.ttl"

VOCABULARY = OntologyVocabulary(
    procedures=("Thủ tục nghỉ học tạm thời",),
    units=("Phòng Đào tạo Đại học",),
    forms=("Mục tải: Đơn xin hoãn thi",),
    programs=("Công nghệ thông tin",),
)


def test_tool_tells_the_model_to_send_keywords_not_sentences() -> None:
    """Hướng dẫn rút câu hỏi thành từ khoá phải tới được mô hình."""

    description = TOOL_SCHEMA["function"]["description"]

    assert "TỪ KHOÁ NGẮN" in description
    assert "Nên:" in description and "Không nên:" in description
    assert "đăng ký học phần" in description
    assert "Hãy hướng dẫn tôi cách đăng ký học phần nhé" in description


def test_tool_passes_the_keyword_list_through_unchanged() -> None:
    function = TOOL_SCHEMA["function"]
    parameters = function["parameters"]

    assert function["name"] == "lookup_academic_information"
    assert parameters["required"] == ["keywords"]
    assert parameters["properties"]["keywords"]["type"] == "array"


def test_tool_description_is_the_shared_constant() -> None:
    assert TOOL_SCHEMA["function"]["description"] == TOOL_DESCRIPTION


def test_tool_teaches_the_model_to_read_the_search_result() -> None:
    description = TOOL_SCHEMA["function"]["description"]

    assert "JSON" in description and "DANH SÁCH" in description
    for key in ("status=found", "status=not_found", "results", "matched", "sources", "citation",
                "facts", "incoming", "unmatched", "truncation"):
        assert key in description, key
    # Kiểm dòng khớp là chốt chặn khi tìm kiếm trả về một mục không đúng ý hỏi.
    assert "Kiểm `matched` TRƯỚC" in description
    assert "ĐỪNG gọi lại" in description
    assert f"tối đa {MAX_KEYWORDS_PER_LOOKUP} từ khoá" in description
    assert f"tối đa\n{MAX_KEYWORD_CHARACTERS} ký tự" in description or f"tối đa {MAX_KEYWORD_CHARACTERS} ký tự" in description


def test_instructions_name_what_the_assistant_can_look_up() -> None:
    """Khuôn nhắc nêu phạm vi dữ liệu bằng tên người dùng quen gọi."""

    instructions = build_instructions(VOCABULARY)

    for name in ("nghỉ học tạm thời", "Phòng Đào tạo Đại học", "Đơn xin hoãn thi", "Công nghệ thông tin"):
        assert name in instructions, name


def test_instructions_forbid_answering_from_memory() -> None:
    """Ranh giới của hệ thống: mô hình diễn đạt, đồ thị giữ dữ kiện."""

    instructions = build_instructions(VOCABULARY)

    assert "đừng suy đoán" in instructions
    assert "đừng bịa số" in instructions
    # Quy tắc gọi công cụ phải đứng TRƯỚC danh sách chủ đề.
    assert instructions.index("GỌI `lookup_academic_information` TRƯỚC") < instructions.index("Thủ tục:")
    assert "`matched`" in instructions
    assert "trích dẫn" in instructions and "đường dẫn" in instructions


def test_instructions_keep_multi_topic_and_no_inference_rules() -> None:
    instructions = build_instructions(VOCABULARY)

    assert "Câu hỏi có nhiều chủ đề độc lập" in instructions
    assert "không bỏ sót vế nào" in instructions
    assert "bảng chung cho một ngành cụ thể" in instructions


def test_instructions_without_vocabulary_have_no_topic_list() -> None:
    instructions = build_instructions()

    assert "Thủ tục:" not in instructions
    assert "lookup_academic_information" in instructions


def test_system_prompt_stays_below_four_hundred_words() -> None:
    assert len(build_instructions(VOCABULARY).split()) < 400


def test_vocabulary_is_read_from_the_ontology_being_served() -> None:
    """Danh sách chép tay mục dần; tên trong khuôn nhắc phải đến từ dữ liệu."""

    vocabulary = read_vocabulary(Ontology.from_source(TurtleFileSource(MINI_ONTOLOGY)))

    assert vocabulary.procedures == ("Thủ tục nghỉ học tạm thời",)
    assert vocabulary.units == ("Phòng Công tác Chính trị và Sinh viên",)
    assert vocabulary.forms == () and vocabulary.programs == ()
    assert "nghỉ học tạm thời" in build_instructions(vocabulary)
