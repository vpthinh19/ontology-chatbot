"""Tests for ``ontchatbot.ontology.fuzzy``."""

from __future__ import annotations

from ontchatbot.ontology.fuzzy import _norm, best, search


def test_norm_strips_diacritics_and_punct():
    assert _norm("Đăng ký môn học!") == "dang ky mon hoc"
    assert _norm("Phòng CTSV") == "phong ctsv"


def test_search_returns_ranked_matches(onto):
    hits = search("phòng đào tạo", "PhongBanHanhChinh", top_k=3)
    assert hits, "matcher should resolve 'phòng đào tạo'"
    assert hits[0].iri == "PhongDaoTaoDaiHoc"
    assert hits[0].score > hits[-1].score - 1e-6  # non-strict ranking


def test_best_returns_none_below_threshold(onto):
    assert best("xyz hoàn toàn vô nghĩa", "QuyTrinhHocVu") is None


def test_best_resolves_alias_with_typos(onto):
    m = best("hoc lai", "QuyTrinhHocVu")
    assert m is not None and m.iri == "QuyTrinh_HocLai"


def test_fee_short_form_matches(onto):
    m = best("k65", "DinhMucHocPhi")
    assert m is not None and m.iri.startswith("Phi_K65_")
