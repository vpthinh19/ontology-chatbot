"""Dòng chỉ mục: ba loại dòng, trỏ về node gốc, không có thuộc tính kỹ thuật."""

from __future__ import annotations

from ontchatbot.search import EntryKind, IndexBuilder


def _entries(ontology):
    return IndexBuilder(ontology).build_entries()


def test_every_individual_yields_label_datatype_and_object_property_rows(mini_ontology) -> None:
    rows = {(entry.kind, entry.text) for entry in _entries(mini_ontology)}

    assert (EntryKind.LABEL, "Thủ tục nghỉ học tạm thời") in rows
    assert (EntryKind.LABEL, "bảo lưu kết quả học tập") in rows
    assert (EntryKind.DATATYPE_PROPERTY, "Phòng Công tác Chính trị và Sinh viên | điện thoại") in rows
    assert (
        EntryKind.OBJECT_PROPERTY,
        "Thủ tục nghỉ học tạm thời | nộp tại | Phòng Công tác Chính trị và Sinh viên",
    ) in rows


def test_rows_of_a_component_point_to_the_procedure_that_contains_it(mini_ontology) -> None:
    """Tìm trúng một bước thì kết quả phải là cả thủ tục, không phải riêng bước đó."""

    step_row = next(
        entry for entry in _entries(mini_ontology)
        if entry.text == "Nghỉ học tạm thời - bước 1 | do ai thực hiện | Sinh viên"
    )

    assert step_row.node == ":LeaveProcedure"
    assert step_row.subject == ":LeaveStep01"
    assert step_row.property == ":performedBy"
    assert step_row.target == ":Student"


def test_technical_properties_never_become_rows(mini_ontology) -> None:
    """Người hỏi không hỏi theo căn cứ, trích dẫn, đường dẫn hay số thứ tự."""

    texts = [entry.text for entry in _entries(mini_ontology)]

    for technical in ("| căn cứ", "| trích dẫn", "| đường dẫn văn bản gốc", "| thứ tự bước", "| nằm trong phần"):
        assert not any(technical in text for text in texts), technical


def test_rows_are_unique(mini_ontology) -> None:
    entries = _entries(mini_ontology)
    keys = [(entry.kind, entry.text, entry.node, entry.property, entry.target) for entry in entries]

    assert len(keys) == len(set(keys))
