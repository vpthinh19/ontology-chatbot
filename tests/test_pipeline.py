"""Pipeline end-to-end: understand → answer → render, over the real graph.

The new pipeline has no injectable NER — the rule-based NLU resolves anchors
through the graph, so these are true integration tests on v8 data.
"""

from __future__ import annotations

import asyncio

import pytest

from ontchatbot.pipeline import Pipeline


@pytest.fixture(scope="module")
def pipe():
    return Pipeline()


def test_greeting_short_circuits(pipe):
    out = pipe.answer("xin chào ạ")
    assert out["entities"] == []
    assert "Xin chào" in out["reply"]


def test_out_of_domain(pipe):
    out = pipe.answer("trận bóng tối qua ai thắng")
    assert "ngoài phạm vi" in out["reply"]


def test_condition_forward_walk(pipe):
    out = pipe.answer("điều kiện bảo lưu là gì")
    assert any(e["iri"] == "QuyTrinhBaoLuu" for e in out["entities"])
    assert "Điều kiện" in out["reply"]


def test_office_self_shows_contact(pipe):
    out = pipe.answer("Phòng CTSV ở đâu")
    assert "ctsv@ntu.edu.vn" in out["reply"]


def test_document_to_office_two_hop(pipe):
    out = pipe.answer("đơn xin nghỉ học tạm thời nộp ở phòng nào")
    assert "Phòng Công tác Sinh viên" in out["reply"]


def test_office_inverse_to_procedures(pipe):
    out = pipe.answer("Phòng CTSV phụ trách gì")
    assert "Thủ tục phụ trách" in out["reply"]
    assert "bảo lưu" in out["reply"].lower()


def test_listing_renders_all(pipe):
    out = pipe.answer("trường có những phòng ban hành chính nào")
    assert "Phòng Công tác Sinh viên" in out["reply"]
    assert out["entities"]


def test_multi_match_fees_via_cohort(pipe):
    out = pipe.answer("học phí k65 thế nào")
    iris = {e["iri"] for e in out["entities"]}
    assert {"HocPhiK65QuanTriKinhDoanh", "HocPhiK65CongNgheThongTin"} <= iris
    assert "550.000" in out["reply"] and "620.000" in out["reply"]


def test_fee_cohort_program_intersects_to_one(pipe):
    # K65 ∩ CNTT → a single fee (620k), not the whole K65 cohort. This is the
    # set GIAO a top-1 similarity score cannot do.
    out = pipe.answer("học phí k65 ngành công nghệ thông tin bao nhiêu")
    iris = {e["iri"] for e in out["entities"]}
    assert iris == {"HocPhiK65CongNgheThongTin"}
    assert "620.000" in out["reply"] and "550.000" not in out["reply"]


def test_eligibility_threshold_verdict(pipe):
    # Structured Condition → a real fail verdict, not a prose dump.
    out = pipe.answer("CPA 5.2 tốt nghiệp được không")
    assert "Chưa đủ điều kiện" in out["reply"]
    assert "5.5" in out["reply"]


def test_async_matches_sync(pipe):
    sync_out = pipe.answer("điều kiện bảo lưu")
    async_out = asyncio.run(pipe.aanswer("điều kiện bảo lưu"))
    assert sync_out == async_out
