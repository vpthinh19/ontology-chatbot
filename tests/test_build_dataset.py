"""Tests for ``ontchatbot.data.build_dataset``."""

from __future__ import annotations

from ontchatbot.data.build_dataset import (
    build,
    collect_surfaces,
    render_single,
    stitch,
)
from ontchatbot.ontology.loader import bio_label_list


def test_collect_surfaces_includes_aliases(onto):
    pool = collect_surfaces()
    for tag in ("QuyTrinhHocVu", "PhongBanHanhChinh", "DinhMucHocPhi",
                "PhuongThucThanhToan", "TaiLieuBieuMau"):
        assert pool[tag], f"{tag} surface pool empty"


def test_render_single_emits_consistent_bio():
    s = render_single("{E} là gì", "QuyTrinhHocVu", "bảo lưu")
    assert len(s["tokens"]) == len(s["ner_tags"])
    assert s["ner_tags"][0] == "B-QuyTrinhHocVu"
    assert "O" in s["ner_tags"]  # "là gì" tokens are O


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
        assert "intent" not in row  # the intent field is gone


def test_build_deterministic(onto):
    a = build(n_per_tag=3, n_multi=2, n_greeting=2, n_ood=2,
              test_ratio=0.25, noise_ratio=0.0, seed=7)
    b = build(n_per_tag=3, n_multi=2, n_greeting=2, n_ood=2,
              test_ratio=0.25, noise_ratio=0.0, seed=7)
    assert a == b
