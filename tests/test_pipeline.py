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
    assert any(e["iri"] == "QuyTrinh_BaoLuu" for e in out["entities"])
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
    assert {"Phi_K65_550k", "Phi_K65_620k"} <= iris
    assert "550.000" in out["reply"] and "620.000" in out["reply"]


def test_async_matches_sync(pipe):
    sync_out = pipe.answer("điều kiện bảo lưu")
    async_out = asyncio.run(pipe.aanswer("điều kiện bảo lưu"))
    assert sync_out == async_out
