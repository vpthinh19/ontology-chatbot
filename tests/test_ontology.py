"""Tests for :class:`ontchatbot.ontology.store.Ontology`.

Covers schema accessors, two-mode fuzzy resolve, and the JSON contract of
:meth:`describe` / :meth:`list_class`.
"""

from __future__ import annotations

import pytest

from ontchatbot.ontology.store import FIXED_KEYS, MatchResult, Ontology


# Schema accessors

def test_tags_lists_only_ontology_backed_classes(ontology: Ontology):
    assert set(ontology.tags) == {
        "QuyTrinhHocVu", "PhongBanHanhChinh", "TaiLieuBieuMau",
        "DinhMucHocPhi", "PhuongThucThanhToan",
    }


def test_bio_labels_size_matches_tags(ontology: Ontology):
    labels = ontology.bio_labels()
    assert labels[0] == "O"
    assert len(labels) == 1 + 2 * len(ontology.tags)
    for tag in ontology.tags:
        assert f"B-{tag}" in labels and f"I-{tag}" in labels


def test_class_local_resolves_uri(ontology: Ontology):
    assert ontology.class_local("QuyTrinhHocVu") == "AcademicProcedure"
    assert ontology.class_local("PhuongThucThanhToan") == "PaymentMethod"


# Fuzzy resolve

def test_resolve_alias_with_typos(ontology: Ontology):
    res = ontology.resolve("hoc lai", "QuyTrinhHocVu")
    assert res.class_won is False
    assert "QuyTrinh_HocLai" in res.individuals


def test_resolve_returns_all_individuals_above_threshold(ontology: Ontology):
    """Ambiguous cohort spans must surface *every* matching fee, not top-1."""
    res = ontology.resolve("k65", "DinhMucHocPhi")
    assert res.class_won is False
    assert set(res.individuals) >= {"Phi_K65_550k", "Phi_K65_620k"}


def test_resolve_class_label_wins_for_class_level_question(ontology: Ontology):
    """``"quy trình học vụ"`` is the class label itself, so the matcher
    should defer to the class-listing template."""
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


# describe — top-level entity

def test_describe_uses_property_labels_as_keys(ontology: Ontology):
    """The whole point of the schema-agnostic contract: section headers
    are Vietnamese ``rdfs:label`` of properties, used directly as keys."""
    d = ontology.describe("QuyTrinh_NopHocPhi")
    assert d is not None
    assert d["type"] == "individual"
    assert d["iri"] == "QuyTrinh_NopHocPhi"
    assert d["class"] == "AcademicProcedure"
    assert d["label"] == "Quy trình đóng học phí"
    # Vietnamese property labels are top-level keys
    assert "Mô tả quy trình" in d
    assert "Được xử lý bởi" in d
    assert "Áp dụng mức học phí" in d


def test_describe_skips_alias(ontology: Ontology):
    """``hasAlias`` is matcher input, never user-facing chat content —
    must be excluded from the JSON contract."""
    d = ontology.describe("QuyTrinh_NopHocPhi")
    assert d is not None
    assert "Từ đồng nghĩa (Alias)" not in d


def test_describe_object_property_recurses_one_level(ontology: Ontology):
    """Object-property targets carry full identity + URL data only."""
    d = ontology.describe("QuyTrinh_NopHocPhi")
    handlers = d["Được xử lý bởi"]
    assert isinstance(handlers, list) and handlers
    target = handlers[0]
    assert target["type"] == "individual"
    assert target["class"] == "AdministrativeOffice"
    assert target["label"] == "Phòng Tài chính"
    # URL-shaped data carried at depth=0
    assert any(isinstance(v, str) and v.startswith("http")
               for k, v in target.items() if k not in FIXED_KEYS)


def test_describe_dataproperty_currency_as_int(ontology: Ontology):
    d = ontology.describe("Phi_K65_550k")
    assert d["Mức học phí/1 Tín chỉ (VNĐ)"] == 550000


def test_describe_unknown_iri_returns_none(ontology: Ontology):
    assert ontology.describe("QuyTrinh_DoesNotExist__") is None


def test_describe_paragraph_property_marked_with_leading_newline(ontology: Ontology):
    """Convention: paragraph properties (procedureDescription, feeNote) are
    emitted with a leading ``\\n``. This is the marker the renderer uses to
    distinguish paragraphs from single-value bullets, regardless of whether
    the underlying text is single-line or multi-line."""
    d = ontology.describe("QuyTrinh_BaoLuu")
    desc = d["Mô tả quy trình"]
    assert isinstance(desc, str)
    assert desc.startswith("\n")  # paragraph marker
    # The marker is always present; multi-line content additionally has
    # internal newlines.
    body = desc.lstrip("\n")
    assert body  # non-empty


# list_class

def test_list_class_emits_every_individual(ontology: Ontology):
    listing = ontology.list_class("QuyTrinhHocVu")
    assert listing["type"] == "listing"
    assert listing["class"] == "AcademicProcedure"
    assert listing["label"] == "Quy trình học vụ"
    labels = {it["label"] for it in listing["items"]}
    assert "Quy trình đóng học phí" in labels
    assert "Quy trình xin bảo lưu kết quả học tập" in labels
