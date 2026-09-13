"""Thêm, sửa, xoá qua lược đồ trên bản sao của ontology thật."""

from __future__ import annotations

import shutil

import pytest

from ontchatbot.admin import AdminError, AdminStore, Conflict, Schema
from ontchatbot.settings import ONTOLOGY_PATH

SHAPES_PATH = ONTOLOGY_PATH.with_name("shapes.ttl")
NEW_CONCEPT = {
    "class": "KhaiNiem",
    "label": "Mục thử của phép kiểm",
    "statements": [
        {"property": "loaiKhaiNiem", "value": "KhaiNiemHocVu"},
        {"property": "noiDung", "value": "Nội dung thử.", "source": "Nguon1052", "coordinate": "khoản 9 Điều 99"},
    ],
}


@pytest.fixture(scope="module")
def schema() -> Schema:
    return Schema.from_file(SHAPES_PATH)


@pytest.fixture
def store(tmp_path, schema) -> AdminStore:
    path = tmp_path / "ontology.trig"
    shutil.copy(ONTOLOGY_PATH, path)
    return AdminStore(path, schema, shapes_path=SHAPES_PATH)


def test_the_schema_describes_each_editable_class_and_its_fields(schema) -> None:
    assert "DiaChiTrichDan" not in schema.classes, "địa chỉ trích dẫn do hệ thống tự quản"
    thu_tuc = schema.classes["ThuTucHocVu"]
    noi_dung = thu_tuc.field("noiDung")
    assert (noi_dung.kind, noi_dung.required, noi_dung.sourced) == ("text", True, True)
    assert (thu_tuc.field("nopTai").kind, thu_tuc.field("nopTai").target) == ("link", "ChuThe")
    assert schema.classes["Nguon"].field("duongDan").sourced is None
    assert "QuyChe" in schema.classes["Nguon"].field("loaiNguon").choices


def test_saving_an_entity_without_changes_leaves_the_file_byte_identical(store) -> None:
    before = store.path.read_bytes()
    entity = store.get("ThuTucNghiHocTamThoi")

    store.update(entity["id"], entity)

    assert store.path.read_bytes() == before


def test_a_new_entity_is_written_with_its_citation_address(store, schema) -> None:
    local = store.create(NEW_CONCEPT)

    reread = AdminStore(store.path, schema, shapes_path=SHAPES_PATH).get(local)
    [sourced] = [s for s in reread["statements"] if s["property"] == "noiDung"]
    assert (sourced["source"], sourced["coordinate"]) == ("Nguon1052", "khoản 9 Điều 99")


def test_a_sourced_field_without_a_source_is_refused_and_nothing_is_written(store) -> None:
    before = store.path.read_bytes()
    payload = {**NEW_CONCEPT, "statements": [NEW_CONCEPT["statements"][0], {"property": "noiDung", "value": "x"}]}

    with pytest.raises(AdminError) as refused:
        store.create(payload)

    assert any("phải chọn nguồn" in reason for reason in refused.value.errors)
    assert store.path.read_bytes() == before


def test_the_schema_check_names_a_missing_required_field(store) -> None:
    with pytest.raises(AdminError) as refused:
        store.create({**NEW_CONCEPT, "statements": [NEW_CONCEPT["statements"][0]]})

    assert refused.value.errors == ["Mục thử của phép kiểm · nội dung: thiếu giá trị bắt buộc"]


def test_an_entity_other_entities_point_to_cannot_be_deleted(store) -> None:
    with pytest.raises(Conflict):
        store.delete("PhongCongTacChinhTriVaSinhVien")


def test_deleting_an_entity_also_removes_the_citation_address_nobody_uses_any_more(store) -> None:
    before = store.path.read_bytes()
    local = store.create(NEW_CONCEPT)
    assert b"kho\xe1\xba\xa3n 9 \xc4\x90i\xe1\xbb\x81u 99" in store.path.read_bytes()

    store.delete(local)

    assert store.path.read_bytes() == before
