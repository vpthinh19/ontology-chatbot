import pytest

from ontchatbot.runtime.render import render_rows


def test_renders_empty_result() -> None:
    assert render_rows([]) == "Không có thông tin."


def test_renders_single_value_without_decoration() -> None:
    assert render_rows([{"answer": "Phòng Công tác Sinh viên"}]) == "Phòng Công tác Sinh viên"


def test_renders_multiple_values_as_list() -> None:
    assert render_rows([{"answer": "A"}, {"answer": "B"}]) == "- A\n- B"


def test_renders_multiple_columns_without_ontology_dto() -> None:
    assert render_rows([{"document": "Đơn bảo lưu", "url": "https://example.com"}]) == (
        "document: Đơn bảo lưu; url: https://example.com"
    )


def test_rejects_inconsistent_columns() -> None:
    with pytest.raises(ValueError, match="same columns"):
        render_rows([{"answer": "A"}, {"value": "B"}])
