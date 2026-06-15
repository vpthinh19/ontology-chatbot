"""NLU baseline: lexicon scan → subject + constraints, greeting, scope notice.

Uses the real graph lexicon (session fixture) — the scanner is meaningless
without it, and these double as integration checks of the danh bạ.
"""

from __future__ import annotations

import pytest

from ontchatbot.nlu import GREETING, QUERY, understand


@pytest.fixture(scope="module")
def lex(graph):
    return graph.lexicon()


def test_greeting_act(lex):
    q = understand("xin chào ạ", lex)
    assert q.act == GREETING and not q.constraints


def test_thanks_is_greeting(lex):
    assert understand("cảm ơn nhé", lex).act == GREETING


def test_subject_class_with_constraint(lex):
    q = understand("điều kiện bảo lưu", lex)
    assert q.act == QUERY
    assert q.subject_cls == "DieuKien"
    assert [(m.cls, m.iri) for m in q.constraints] == [("QuyTrinhHocVu", "QuyTrinhBaoLuu")]


def test_multi_constraint_mixed_classes(lex):
    # The flagship: subject "học phí" + cohort/program/cohort constraints.
    q = understand("học phí k65 cntt với k67 như nào", lex)
    assert q.subject_cls == "DinhMucHocPhi"
    assert [(m.cls, m.iri) for m in q.constraints] == [
        ("Khoa", "KhoaK65"),
        ("Nganh", "NganhCongNgheThongTin"),
        ("Khoa", "KhoaK67"),
    ]


def test_listing_subject_has_no_constraint(lex):
    q = understand("trường có những phòng ban hành chính nào", lex)
    assert q.subject_cls == "PhongBanHanhChinh"
    assert q.subject_listable and not q.constraints


def test_second_subject_reported_as_extra(lex):
    # One subject per query; the office ask is surfaced for the notice.
    q = understand("học phí k65 bao nhiêu và nộp ở đâu", lex)
    assert q.subject_cls == "DinhMucHocPhi"
    assert q.extra_subjects == ["PhongBanHanhChinh"]


def test_self_description_no_subject_mention(lex):
    # No class word; the named individual carries the query.
    q = understand("Phòng Công tác Sinh viên ở đâu", lex)
    assert q.subject_cls == ""
    assert [m.iri for m in q.constraints] == ["PhongCongTacSinhVien"]


def test_out_of_domain_has_no_mentions(lex):
    q = understand("thời tiết hôm nay thế nào", lex)
    assert q.act == QUERY and not q.constraints and q.subject_cls == ""
