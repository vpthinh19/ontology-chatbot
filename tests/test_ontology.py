"""Tests for :class:`ontchatbot.ontology.Ontology`."""

from __future__ import annotations

import pytest

from ontchatbot.ontology import FIXED_KEYS, MatchResult, Ontology


def test_tags_lists_only_ontology_backed_classes(ontology: Ontology):
    assert set(ontology.tags) == {
        "QuyTrinhHocVu", "PhongBanHanhChinh", "TaiLieuBieuMau",
        "DinhMucHocPhi", "PhuongThucThanhToan",
    }


def test_class_local_resolves_uri(ontology: Ontology):
    assert ontology.class_local("QuyTrinhHocVu") == "AcademicProcedure"
    assert ontology.class_local("PhuongThucThanhToan") == "PaymentMethod"


# Fuzzy resolve

def test_resolve_alias_with_typos(ontology: Ontology):
    res = ontology.resolve("hoc lai", "QuyTrinhHocVu")
    assert res.class_won is False
    assert "QuyTrinh_HocLai" in res.individuals


def test_resolve_returns_all_individuals_above_threshold(ontology: Ontology):
    """Ambiguous cohort spans surface every matching fee, not just top-1."""
    res = ontology.resolve("k65", "DinhMucHocPhi")
    assert res.class_won is False
    assert set(res.individuals) >= {"Phi_K65_550k", "Phi_K65_620k"}


def test_resolve_class_label_wins_for_class_level_question(ontology: Ontology):
    """Class-label match → class-listing template."""
    res = ontology.resolve("quy trình học vụ", "QuyTrinhHocVu")
    assert res.class_won is True
    assert res.individuals == []


def test_resolve_specific_question_zooms_to_individual(ontology: Ontology):
    res = ontology.resolve("đóng học phí", "QuyTrinhHocVu")
    assert res.class_won is False
    assert "QuyTrinh_NopHocPhi" in res.individuals


def test_resolve_below_threshold_returns_empty(ontology: Ontology):
    res = ontology.resolve("xyz hoàn toàn vô nghĩa", "QuyTrinhHocVu")
    assert res.class_won is False
    assert res.individuals == []


def test_resolve_rejects_visual_collision(ontology: Ontology):
    """Regression: ``"rớt môn"`` (= học lại) must not also match ``"rút môn"``
    (= drop course). Token-set ratio scores them ≈ 86 — threshold 88 filters."""
    res = ontology.resolve("rớt môn", "QuyTrinhHocVu")
    assert res.class_won is False
    assert "QuyTrinh_HocLai" in res.individuals
    assert "QuyTrinh_RutMonHoc" not in res.individuals


# describe — top-level entity

def test_describe_uses_property_labels_as_keys(ontology: Ontology):
    """Property rdfs:label is used directly as the JSON key."""
    d = ontology.describe("QuyTrinh_NopHocPhi")
    assert d is not None
    assert d["type"] == "individual"
    assert d["iri"] == "QuyTrinh_NopHocPhi"
    assert d["class"] == "AcademicProcedure"
    assert d["label"] == "Quy trình đóng học phí"
    assert "Mô tả quy trình" in d
    assert "Được xử lý bởi" in d
    assert "Áp dụng mức học phí" in d


def test_describe_skips_alias(ontology: Ontology):
    """``hasAlias`` is matcher input, never user-facing chat content."""
    d = ontology.describe("QuyTrinh_NopHocPhi")
    assert d is not None
    assert "Từ đồng nghĩa (Alias)" not in d


def test_describe_object_property_recurses_one_level(ontology: Ontology):
    d = ontology.describe("QuyTrinh_NopHocPhi")
    handlers = d["Được xử lý bởi"]
    assert isinstance(handlers, list) and handlers
    target = handlers[0]
    assert target["type"] == "individual"
    assert target["class"] == "AdministrativeOffice"
    assert target["label"] == "Phòng Tài chính"
    assert any(isinstance(v, str) and v.startswith("http")
               for k, v in target.items() if k not in FIXED_KEYS)


def test_describe_dataproperty_currency_as_int(ontology: Ontology):
    d = ontology.describe("Phi_K65_550k")
    assert d["Mức học phí/1 Tín chỉ (VNĐ)"] == 550000


def test_describe_unknown_iri_returns_none(ontology: Ontology):
    assert ontology.describe("QuyTrinh_DoesNotExist__") is None


def test_describe_paragraph_property_marked_with_leading_newline(ontology: Ontology):
    """Convention: paragraph values carry a leading ``\\n`` as marker."""
    d = ontology.describe("QuyTrinh_BaoLuu")
    desc = d["Mô tả quy trình"]
    assert isinstance(desc, str) and desc.startswith("\n")
    assert desc.lstrip("\n")  # non-empty body


def test_list_class_emits_every_individual(ontology: Ontology):
    listing = ontology.list_class("QuyTrinhHocVu")
    assert listing["type"] == "listing"
    assert listing["class"] == "AcademicProcedure"
    assert listing["label"] == "Quy trình học vụ"
    labels = {it["label"] for it in listing["items"]}
    assert "Quy trình đóng học phí" in labels
    assert "Quy trình xin bảo lưu kết quả học tập" in labels


def test_describe_dedupes_predicate_target_from_ancestor(ontology: Ontology):
    """Each fee category links the same regulation as its parent procedure.
    The dedup mechanism drops the duplicate ``basedOnRegulation`` link from
    every fee target so the parent's link remains the only assertion."""
    d = ontology.describe("QuyTrinh_NopHocPhi", depth=2)
    # Parent has the link.
    assert "Căn cứ theo quy định" in d
    # Each fee category target has lost the duplicate link.
    fees = d["Áp dụng mức học phí"]
    for fee in fees:
        assert "Căn cứ theo quy định" not in fee, (
            f"fee {fee['iri']} should drop the parent's regulation link "
            f"(got keys {list(fee.keys())})"
        )
