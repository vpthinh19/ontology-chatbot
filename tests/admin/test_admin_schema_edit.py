"""Sửa loại, thuộc tính và định danh ở trang quản trị, trên bản sao của ontology thật."""

from __future__ import annotations

import shutil

import pytest

from ontchatbot.admin import AdminError, AdminStore, Schema
from ontchatbot.settings import ONTOLOGY_PATH

SHAPES_PATH = ONTOLOGY_PATH.with_name("shapes.ttl")
NGUON = {"source": "Nguon1052", "coordinate": "khoản 9 Điều 99"}


@pytest.fixture
def store(tmp_path) -> AdminStore:
    shutil.copy(ONTOLOGY_PATH, tmp_path / "ontology.trig")
    shutil.copy(SHAPES_PATH, tmp_path / "shapes.ttl")
    return AdminStore(tmp_path / "ontology.trig", Schema.from_file(tmp_path / "shapes.ttl"))


def field(prop, name, kind, **extra):
    return {"property": prop, "name": name, "kind": kind, "required": False, "single": False, "sourced": True, **extra}


def new_class(**extra) -> dict:
    return {
        "name": "QuyDinhThu",
        "label": "Quy định thử",
        "altLabels": True,
        "fields": [
            field("noiDung", "nội dung", "text", required=True),
            field("coQuanBanHanh", "cơ quan ban hành", "link", target="ChuThe"),
            field("mucDoThu", "mức độ thử", "choice", sourced=False, single=True,
                  choices=[{"id": "MucDoCao", "label": "mức cao"}, {"id": "MucDoThap", "label": "mức thấp"}]),
        ],
        **extra,
    }


def member(label="Quy định mẫu") -> dict:
    return {"class": "QuyDinhThu", "label": label, "statements": [
        {"property": "noiDung", "value": "Một quy định.", **NGUON},
        {"property": "coQuanBanHanh", "value": "PhongDaoTaoDaiHoc", **NGUON},
        {"property": "mucDoThu", "value": "MucDoCao"},
    ]}


def test_the_shapes_file_is_written_back_byte_for_byte() -> None:
    assert Schema.from_file(SHAPES_PATH).to_turtle() == SHAPES_PATH.read_bytes()


def test_a_new_class_with_its_properties_can_hold_entities(store) -> None:
    assert store.save_class(None, new_class()) == "QuyDinhThu"

    local = store.create(member())

    reread = AdminStore(store.path, Schema.from_file(store.shapes_path))
    assert reread.get(local)["class"] == "QuyDinhThu"
    assert [f.property for f in reread.schema.classes["QuyDinhThu"].fields] == ["noiDung", "coQuanBanHanh", "mucDoThu"]
    assert reread.label("QuyDinhThu") == "Quy định thử", "engine gọi tên loại bằng nhãn trong ontology.trig"
    assert (reread.label("coQuanBanHanh"), reread.label("MucDoCao")) == ("cơ quan ban hành", "mức cao")


def test_adding_then_removing_a_class_leaves_both_files_byte_identical(store) -> None:
    before = store.path.read_bytes(), store.shapes_path.read_bytes()
    store.save_class(None, new_class())
    local = store.create(member())

    store.delete(local)
    store.delete_class("QuyDinhThu")

    assert (store.path.read_bytes(), store.shapes_path.read_bytes()) == before


def test_renaming_a_class_retypes_its_entities_and_the_fields_that_point_to_it(store) -> None:
    store.save_class(None, new_class())
    local = store.create(member())
    spec = store.schema.classes["QuyDinhThu"]
    payload = {"name": "QuyDinhDaDoi", "label": "Quy định đã đổi", "altLabels": True,
               "version": store.class_version("QuyDinhThu"),
               "fields": [{**field(f.property, f.name, f.kind, required=f.required, single=f.single, sourced=f.sourced,
                                   target=f.target, choices=[{"id": c, "label": store.label(c)} for c in f.choices]),
                           "was": f.property} for f in spec.fields]
               + [field("quyDinhLienQuan", "quy định liên quan", "link", target="QuyDinhThu")]}

    assert store.save_class("QuyDinhThu", payload) == "QuyDinhDaDoi"

    assert store.get(local)["class"] == "QuyDinhDaDoi"
    assert store.schema.classes["QuyDinhDaDoi"].field("quyDinhLienQuan").target == "QuyDinhDaDoi"
    assert "QuyDinhThu" not in store.schema.all_classes and store.label("QuyDinhThu") == "QuyDinhThu"


def test_renaming_a_property_renames_it_in_every_statement(store) -> None:
    store.save_class(None, new_class())
    local = store.create(member())
    spec = store.schema.classes["QuyDinhThu"]
    fields = [{**field(f.property, f.name, f.kind, required=f.required, single=f.single, sourced=f.sourced,
                       target=f.target, choices=[{"id": c, "label": store.label(c)} for c in f.choices]),
               "was": f.property} for f in spec.fields]
    fields[1] = {**fields[1], "property": "donViBanHanh", "name": "đơn vị ban hành"}

    store.save_class("QuyDinhThu", {**new_class(), "fields": fields})

    assert {s["property"] for s in store.get(local)["statements"]} == {"noiDung", "donViBanHanh", "mucDoThu"}
    assert store.label("donViBanHanh") == "đơn vị ban hành"


def test_dropping_a_field_that_holds_data_asks_first_then_removes_its_statements(store) -> None:
    store.save_class(None, new_class())
    local = store.create(member())
    without = {**new_class(), "fields": new_class()["fields"][:2]}

    with pytest.raises(AdminError) as asked:
        store.save_class("QuyDinhThu", without)
    assert (asked.value.status, asked.value.confirm) == (409, True)
    assert "mức độ thử: 1 quan hệ" in asked.value.errors

    store.save_class("QuyDinhThu", {**without, "confirm": True})
    assert "mucDoThu" not in {s["property"] for s in store.get(local)["statements"]}


def test_a_stricter_schema_that_existing_data_breaks_is_refused_with_the_entities_named(store) -> None:
    store.save_class(None, new_class())
    store.create(member())
    stricter = new_class()
    stricter["fields"][1] = {**stricter["fields"][1], "required": True}
    store.create({**member("Quy định không có cơ quan"), "statements": member()["statements"][::2]})

    with pytest.raises(AdminError) as refused:
        store.save_class("QuyDinhThu", stricter)

    assert refused.value.errors == ["Quy định không có cơ quan · cơ quan ban hành: thiếu giá trị bắt buộc"]


def test_a_class_with_entities_or_used_by_the_code_cannot_be_deleted(store) -> None:
    for name in ("KhaiNiem", "ThuTucHocVu"):
        with pytest.raises(AdminError) as refused:
            store.delete_class(name)
        assert refused.value.status == 409


def test_names_the_code_relies_on_cannot_be_renamed(store) -> None:
    spec = store.schema.classes["Nguon"]
    payload = {"name": "NguonTaiLieu", "label": spec.label, "altLabels": False,
               "fields": [{**field(f.property, f.name, f.kind, required=f.required, single=f.single, sourced=f.sourced,
                                   target=f.target, choices=[{"id": c, "label": store.label(c)} for c in f.choices]),
                           "was": f.property} for f in spec.fields]}

    with pytest.raises(AdminError) as refused:
        store.save_class("Nguon", payload)

    assert refused.value.details[0]["where"] == "name"


def test_a_bad_class_form_names_each_wrong_field(store) -> None:
    payload = new_class(name="quyDinh", fields=[field("NoiDung", "", "text"), field("x", "x", "link", target="Khong")])

    with pytest.raises(AdminError) as refused:
        store.save_class(None, payload)

    wrong = {(d.get("where"), d.get("field"), d.get("key")) for d in refused.value.details}
    assert wrong == {("name", None, None), (None, 0, "property"), (None, 0, "name"), (None, 1, "target")}


def test_an_entity_can_change_its_identifier_and_every_reference_follows(store) -> None:
    entity = store.get("PhongDaoTaoDaiHoc")
    pointing = [r["id"] for r in entity["references"]]

    assert store.update("PhongDaoTaoDaiHoc", {**entity, "id": "PhongDaoTaoMoi"}) == "PhongDaoTaoMoi"

    assert [r["id"] for r in store.get("PhongDaoTaoMoi")["references"]] == pointing
    with pytest.raises(AdminError):
        store.get("PhongDaoTaoDaiHoc")


def test_a_second_tab_saving_an_outdated_form_is_refused(store) -> None:
    first, second = store.get("HocKyHe"), store.get("HocKyHe")
    store.update("HocKyHe", {**first, "altLabels": first["altLabels"] + ["tên từ tab thứ nhất"]})

    with pytest.raises(AdminError) as refused:
        store.update("HocKyHe", {**second, "altLabels": second["altLabels"] + ["tên từ tab thứ hai"]})

    assert refused.value.status == 409
    assert "tên từ tab thứ nhất" in store.get("HocKyHe")["altLabels"]


def test_errors_point_at_the_row_the_editor_sees(store) -> None:
    payload = {"class": "KhaiNiem", "label": "Mục thử", "statements": [
        {"row": 0, "property": "loaiKhaiNiem", "value": "KhaiNiemHocVu", "coordinate": "Điều 1"},
        {"row": 2, "property": "noiDung", "value": "x", "source": "Nguon1052"},
    ]}

    with pytest.raises(AdminError) as refused:
        store.create(payload)

    assert [(d["row"], d["message"].split(":")[0]) for d in refused.value.details] == [
        (0, "Quan hệ 1 (loại khái niệm)"), (2, "Quan hệ 3 (nội dung)")]


def test_a_source_link_must_be_a_web_address(store) -> None:
    with pytest.raises(AdminError) as refused:
        store.create({"class": "Nguon", "label": "Nguồn thử", "statements": [
            {"property": "loaiNguon", "value": "QuyChe"}, {"property": "duongDan", "value": "khong phai url"}]})

    assert "không phải địa chỉ web" in refused.value.errors[0]


def test_deleting_a_cited_source_names_the_entities_that_cite_it(store) -> None:
    with pytest.raises(AdminError) as refused:
        store.delete("Nguon1052")

    assert "Thủ tục nghỉ học tạm thời · trích dẫn nguồn này" in refused.value.errors
