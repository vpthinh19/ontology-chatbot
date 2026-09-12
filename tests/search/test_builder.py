"""Dòng chỉ mục: ba loại dòng, giá trị không vào chỉ mục."""

from __future__ import annotations

from ontchatbot.search import EntryKind, IndexBuilder


def _texts(entries, kind: EntryKind) -> set[str]:
    return {entry.text for entry in entries if entry.kind is kind}


def test_every_name_of_an_entity_becomes_a_row(mini_ontology) -> None:
    """Tên gọi phụ cũng phải tìm được, nếu không thì thêm altLabel là vô ích."""

    entries = IndexBuilder(mini_ontology).build_entries()

    labels = _texts(entries, EntryKind.LABEL)
    assert "Thủ tục nghỉ học tạm thời" in labels
    assert "bảo lưu kết quả học tập" in labels


def test_a_datatype_row_names_the_property_but_not_its_value(mini_ontology) -> None:
    """Người ta hỏi "học phí ngành nào", không hỏi theo con số. Giá trị đến tay mô
    hình ở bước đọc hồ sơ, không phải ở chỉ mục."""

    entries = IndexBuilder(mini_ontology).build_entries()

    assert "Thủ tục nghỉ học tạm thời | nội dung" in _texts(entries, EntryKind.DATATYPE_PROPERTY)
    assert not any("Mẫu số 09" in text for text in _texts(entries, EntryKind.DATATYPE_PROPERTY))


def test_an_object_row_carries_both_ends_of_the_relation(mini_ontology) -> None:
    entries = IndexBuilder(mini_ontology).build_entries()

    assert ("Thủ tục nghỉ học tạm thời | nộp tại | Phòng Công tác sinh viên"
            in _texts(entries, EntryKind.OBJECT_PROPERTY))


def test_the_source_layer_produces_no_rows(mini_ontology) -> None:
    """Nguồn và địa chỉ trích dẫn là bộ máy dẫn nguồn, không ai hỏi tới chúng."""

    entries = IndexBuilder(mini_ontology).build_entries()

    assert not any(entry.node.startswith((":Nguon", ":TD")) for entry in entries)
    assert not any("toạ độ" in entry.text or "thuộc nguồn" in entry.text for entry in entries)


def test_a_row_points_at_the_entity_it_describes(mini_ontology) -> None:
    entries = IndexBuilder(mini_ontology).build_entries()

    row = next(e for e in entries if e.text == "bảo lưu kết quả học tập")
    assert row.node == ":ThuTucNghiHocTamThoi"
