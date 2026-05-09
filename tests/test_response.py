"""Tests for ``ontchatbot.ontology.response``."""

from __future__ import annotations

from ontchatbot.ontology.fuzzy import FuzzyMatch
from ontchatbot.ontology.response import (
    GREETING_REPLY,
    OUT_OF_DOMAIN_REPLY,
    compose,
    render_blocks,
    render_one,
)


def test_render_one_quy_trinh(onto):
    out = render_one("QuyTrinhHocVu", "QuyTrinh_BaoLuu")
    assert out and "bảo lưu" in out.lower()
    assert "Phòng" in out


def test_render_one_phong_ban(onto):
    out = render_one("PhongBanHanhChinh", "PhongCTSV")
    assert out and "ctsv@ntu.edu.vn" in out


def test_render_one_unknown_returns_none(onto):
    assert render_one("QuyTrinhHocVu", "QuyTrinh_DoesNotExist__") in (None, "")


def test_render_blocks_dedupes(onto):
    m = FuzzyMatch(iri="PhongCTSV", surface="ctsv", score=99.0)
    out = render_blocks([("PhongBanHanhChinh", m), ("PhongBanHanhChinh", m)])
    # both occurrences fold into a single block
    assert out.count("ctsv@ntu.edu.vn") == 1


def test_compose_greeting_only():
    assert compose("", greeting=True).strip() == GREETING_REPLY


def test_compose_ood_only():
    assert compose("", greeting=False).strip() == OUT_OF_DOMAIN_REPLY


def test_compose_block_takes_priority_over_greeting():
    # Minimal-greeting policy: substantive answers do NOT prepend a greeting,
    # even if the user said "xin chào" first. The bot greets back only when
    # the message is a pure greeting with no recognised entity.
    assert compose("BLOCK", greeting=True).strip() == "BLOCK"


def test_compose_block_only():
    assert compose("BLOCK", greeting=False).strip() == "BLOCK"
