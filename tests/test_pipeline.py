"""Pipeline end-to-end: understand → answer → render, over the real graph.

True integration tests on v9 data: the rule-based NLU scans the graph lexicon,
so there is no injectable NER to stub.
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
    iris = {e["iri"] for e in out["entities"]}
    assert {"DieuKienBaoLuuCaNhan", "DieuKienBaoLuuYTe"} <= iris
    assert "Điều kiện áp dụng" in out["reply"]


def test_office_self_shows_contact(pipe):
    out = pipe.answer("Phòng CTSV ở đâu")
    assert "ctsv@ntu.edu.vn" in out["reply"]


def test_document_to_office_two_hop(pipe):
    out = pipe.answer("đơn xin nghỉ học tạm thời nộp ở đâu")
    assert "Phòng Công tác Sinh viên" in out["reply"]


def test_office_inverse_to_procedures(pipe):
    out = pipe.answer("Phòng CTSV phụ trách gì")
    assert "bảo lưu" in out["reply"].lower()


def test_listing_renders_all(pipe):
    out = pipe.answer("trường có những phòng ban hành chính nào")
    assert "Phòng Công tác Sinh viên" in out["reply"]
    assert len(out["entities"]) == 4


def test_multi_match_fees_via_cohort(pipe):
    out = pipe.answer("học phí k65 thế nào")
    iris = {e["iri"] for e in out["entities"]}
    assert {"HocPhiK65QuanTriKinhDoanh", "HocPhiK65CongNgheThongTin"} <= iris
    assert "550.000" in out["reply"] and "620.000" in out["reply"]


def test_fee_cohort_program_intersection(pipe):
    # The flagship: K65 ∩ CNTT collapses to one fee, the set GIAO no
    # similarity score can express.
    out = pipe.answer("học phí k65 ngành công nghệ thông tin bao nhiêu")
    iris = {e["iri"] for e in out["entities"]}
    assert iris == {"HocPhiK65CongNgheThongTin"}
    assert "620.000" in out["reply"] and "550.000" not in out["reply"]


def test_dnf_union_of_groups(pipe):
    out = pipe.answer("học phí k65 cntt với k67 như nào")
    iris = {e["iri"] for e in out["entities"]}
    assert iris == {"HocPhiK65CongNgheThongTin",
                    "HocPhiK67KinhTeQuanLy", "HocPhiK67KyThuat"}


def test_second_subject_notice(pipe):
    out = pipe.answer("học phí k65 bao nhiêu và nộp ở đâu")
    assert "550.000" in out["reply"]
    assert "hỏi riêng" in out["reply"]


def test_async_matches_sync(pipe):
    sync_out = pipe.answer("điều kiện bảo lưu")
    async_out = asyncio.run(pipe.aanswer("điều kiện bảo lưu"))
    assert sync_out == async_out
