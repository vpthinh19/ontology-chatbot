"""Tests for ``ontchatbot.data.build_dataset``."""

from __future__ import annotations

import re

from ontchatbot.data.build_dataset import (
    build,
    collect_surfaces,
    looks_like_iri,
    render_single,
    stitch,
)
from ontchatbot.ontology.loader import bio_label_list


_CAMEL = re.compile(r"[A-Za-z][a-z]+[A-Z][A-Za-z]")  # e.g. "DonXin", "QuyTrinh"


def test_looks_like_iri_detects_camel_case():
    assert looks_like_iri("DonXinBaoLuu")
    assert looks_like_iri("PhongCTSV")
    assert not looks_like_iri("Đơn xin bảo lưu")
    assert not looks_like_iri("phòng đào tạo")


def test_collect_surfaces_excludes_iris(onto):
    pool = collect_surfaces()
    for tag, forms in pool.items():
        assert forms, f"{tag} surface pool empty"
        for f in forms:
            assert not looks_like_iri(f), f"{tag}: surface '{f}' looks like an IRI"


def test_render_single_emits_consistent_bio():
    s = render_single("{E} là gì", "QuyTrinhHocVu", "bảo lưu")
    assert len(s["tokens"]) == len(s["ner_tags"])
    assert s["ner_tags"][0] == "B-QuyTrinhHocVu"
    assert "O" in s["ner_tags"]


def test_stitch_concatenates_two_samples():
    a = render_single("{E} là gì", "QuyTrinhHocVu", "bảo lưu")
    b = render_single("{E} ở đâu", "PhongBanHanhChinh", "phòng đào tạo")
    out = stitch(a, b, " còn ")
    assert any(t.startswith("B-QuyTrinhHocVu") for t in out["ner_tags"])
    assert any(t.startswith("B-PhongBanHanhChinh") for t in out["ner_tags"])


def test_build_produces_valid_bio(onto):
    train, test = build(n_per_tag=5, n_multi=4, n_greeting=4, n_ood=4,
                        test_ratio=0.25, noise_ratio=0.0, seed=1)
    valid = set(bio_label_list())
    for row in train + test:
        assert len(row["tokens"]) == len(row["ner_tags"])
        for t in row["ner_tags"]:
            assert t in valid


def test_build_no_iri_tokens(onto):
    """Defensive: the rendered samples must never contain CamelCase IRI tokens."""
    train, test = build(n_per_tag=8, n_multi=8, n_greeting=4, n_ood=4,
                        test_ratio=0.25, noise_ratio=0.0, seed=11)
    for row in train + test:
        for tok in row["tokens"]:
            piece = tok.replace("_", " ")
            assert not _CAMEL.search(piece), f"IRI-like token leaked: {tok!r}"


def test_build_no_intent_field(onto):
    train, _ = build(n_per_tag=3, n_multi=2, n_greeting=2, n_ood=2,
                     test_ratio=0.25, noise_ratio=0.0, seed=2)
    for row in train:
        assert set(row.keys()) == {"tokens", "ner_tags"}


def test_build_deterministic(onto):
    a = build(n_per_tag=3, n_multi=2, n_greeting=2, n_ood=2,
              test_ratio=0.25, noise_ratio=0.0, seed=7)
    b = build(n_per_tag=3, n_multi=2, n_greeting=2, n_ood=2,
              test_ratio=0.25, noise_ratio=0.0, seed=7)
    assert a == b
