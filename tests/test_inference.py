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


def test_decode_bio_lenient_treats_orphan_i_as_span_start():
    """Lenient decoding: an ``I-X`` arriving after ``O`` opens a new entity."""
    words = ["xin", "k67", "ạ"]
    tags = ["O", "I-DinhMucHocPhi", "O"]
    spans = decode_bio(words, tags)
    assert len(spans) == 1
    assert spans[0].tag == "DinhMucHocPhi"
    assert spans[0].surface.strip() == "k67"


def test_decode_bio_handles_two_same_class_after_o():
    """Hard case: ``B-X O I-X`` → two entities of the same class."""
    words = ["k65", "và", "k67"]
    tags = ["B-DinhMucHocPhi", "O", "I-DinhMucHocPhi"]
    spans = decode_bio(words, tags)
    assert [s.surface.strip() for s in spans] == ["k65", "k67"]


def test_decode_bio_label_change_breaks_span():
    words = ["a", "b"]
    tags = ["B-QuyTrinhHocVu", "I-PhongBanHanhChinh"]
    spans = decode_bio(words, tags)
    assert len(spans) == 2
    assert spans[0].tag == "QuyTrinhHocVu" and spans[1].tag == "PhongBanHanhChinh"
