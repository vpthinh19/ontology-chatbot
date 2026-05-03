"""Tests for ``ontchatbot.ner.inference`` — focus on the BIO span decoder
since the model itself is heavyweight."""

from __future__ import annotations

from ontchatbot.ner.inference import decode_bio


def test_decode_bio_extracts_single_entity():
    words = ["quy_trình", "bảo_lưu", "ra_sao", "?"]
    tags = ["O", "B-QuyTrinhHocVu", "O", "O"]
    spans = decode_bio(words, tags)
    assert len(spans) == 1
    s = spans[0]
    assert s.tag == "QuyTrinhHocVu"
    assert s.start == 1 and s.end == 2
    assert "bảo lưu" in s.surface


def test_decode_bio_handles_continuation():
    words = ["phòng", "công_tác", "sinh_viên"]
    tags = ["B-PhongBanHanhChinh", "I-PhongBanHanhChinh", "I-PhongBanHanhChinh"]
    spans = decode_bio(words, tags)
    assert len(spans) == 1 and spans[0].end - spans[0].start == 3
    assert "phòng" in spans[0].surface and "sinh viên" in spans[0].surface


def test_decode_bio_extracts_multiple_entities():
    words = ["hp", "k65", "k67", "nữa"]
    tags = ["B-DinhMucHocPhi", "I-DinhMucHocPhi", "B-DinhMucHocPhi", "O"]
    spans = decode_bio(words, tags)
    assert len(spans) == 2
    assert spans[0].surface.strip() == "hp k65"
    assert spans[1].surface.strip() == "k67"


def test_decode_bio_ignores_orphan_i_tags():
    words = ["abc", "xyz"]
    tags = ["I-QuyTrinhHocVu", "O"]
    assert decode_bio(words, tags) == []
