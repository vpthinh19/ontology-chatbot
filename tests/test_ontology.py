"""Ontology: khớp theo type + thuật toán duyệt §5 (chạy trên ontology thật)."""

from __future__ import annotations

from ontchatbot.tree import parse


def _ind(label, *con):
    return {"label": label, "type": "individual", "children": list(con)}


def _obj(label, *con):
    return {"label": label, "type": "object", "children": list(con)}


def _data(label):
    return {"label": label, "type": "data", "children": []}


def _nodes(ont, root):
    return {n.iri for n in ont.traverse(parse({"act": "query", "entities": [root]})).nodes}


# ── Khớp (resolve theo loai) ────────────────────────────────────────────────

def test_khop_individual_strong_alias_wins(ont):
    # alias mạnh "học phí" thắng từng mức phí (chỉ chứa "học phí" trong nhãn dài)
    assert ont.resolve("học phí", "individual") == ["QuyTrinhNopHocPhi"]


def test_khop_individual_cohort_multi(ont):
    assert set(ont.resolve("k65", "individual")) == {"PhiK65550k", "PhiK65620k"}


def test_khop_object_label(ont):
    assert ont.resolve("điều kiện", "object") == "yeuCauDieuKien"
    assert ont.resolve("phòng xử lý", "object") == "duocXuLyBoi"


def test_khop_data_label(ont):
    assert ont.resolve("email", "data") == "email"
    assert ont.resolve("nội dung", "data") == "noiDung"


# ── Duyệt (§5) ──────────────────────────────────────────────────────────────

def test_forward_object_multivalue(ont):
    assert _nodes(ont, _ind("bảo lưu", _obj("điều kiện"))) == {
        "DieuKienBaoLuuCaNhan", "DieuKienBaoLuuQuocTe",
        "DieuKienBaoLuuVuTrang", "DieuKienBaoLuuYTe"}


def test_fee_intersect(ont):
    assert _nodes(ont, _ind("học phí", _ind("k65", _ind("cntt")))) == {"PhiK65620k"}


def test_fee_cohort(ont):
    assert _nodes(ont, _ind("học phí", _ind("k65"))) == {"PhiK65550k", "PhiK65620k"}


def test_fee_union_siblings(ont):
    got = _nodes(ont, _ind("học phí", _ind("k65", _ind("cntt")), _ind("k67")))
    assert got == {"PhiK65620k", "PhiK67550k", "PhiK67620k"}


def test_self_description(ont):
    assert _nodes(ont, _ind("bảo lưu")) == {"QuyTrinhBaoLuu"}


def test_chuyennganh_output_fixed(ont):
    # Sửa lỗi v8 (§6): chuyển ngành → OutputDuocChuyenNganh, KHÔNG phải OutputDuocBaoLuu
    assert _nodes(ont, _ind("chuyển ngành", _obj("kết quả"))) == {"OutputDuocChuyenNganh"}


def test_data_leaf_returns_value_not_node(ont):
    kq = ont.traverse(parse({"act": "query", "entities": [_ind("phòng khtc", _data("email"))]}))
    assert kq.nodes == []
    assert any("khtc@ntu.edu.vn" in str(v) for gv in kq.values for v in gv.values)


def test_root_miss(ont):
    kq = ont.traverse(parse({"act": "query", "entities": [_ind("qwerty zxcvb")]}))
    assert kq.nodes == [] and kq.misses


def test_non_query_yields_empty(ont):
    assert ont.traverse(parse({"act": "greeting", "entities": []})).nodes == []
