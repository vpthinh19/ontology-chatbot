"""Tests for ``ontchatbot.ontology.loader``."""

from __future__ import annotations

from ontchatbot.ontology.loader import (
    bio_label_list,
    class_local,
    iter_individuals,
    load_label_map,
    ontology_tags,
    primary_label,
)


def test_label_map_has_seven_keys(label_map):
    assert len(label_map) == 7
    assert set(label_map) >= {"QuyTrinhHocVu", "PhongBanHanhChinh",
                              "TaiLieuBieuMau", "DinhMucHocPhi",
                              "PhuongThucThanhToan", "ChaoHoi", "NgoaiLe"}


def test_ontology_tags_excludes_normal_intents():
    tags = ontology_tags()
    assert len(tags) == 5
    assert "ChaoHoi" not in tags
    assert "NgoaiLe" not in tags


def test_bio_label_list_size_matches_tags():
    labels = bio_label_list()
    assert labels[0] == "O"
    assert len(labels) == 1 + 2 * len(ontology_tags())
    for tag in ontology_tags():
        assert f"B-{tag}" in labels and f"I-{tag}" in labels


def test_class_local_resolves_uri():
    assert class_local("QuyTrinhHocVu") == "AcademicProcedure"
    assert class_local("PhongBanHanhChinh") == "AdministrativeOffice"
    assert class_local("PhuongThucThanhToan") == "PaymentMethod"


def test_iter_individuals_per_class(onto):
    expected = {
        "AcademicProcedure": 9,
        "AdministrativeOffice": 4,
        "Document": 5,
        "FeeCategory": 10,
        "PaymentMethod": 2,
    }
    for cls, n in expected.items():
        assert len(list(iter_individuals(cls))) == n, cls


def test_primary_label_returns_string(onto):
    inds = list(iter_individuals("AdministrativeOffice"))
    assert inds, "ontology has at least one office"
    label = primary_label(inds[0])
    assert isinstance(label, str) and label.strip()
