"""Tests for ``ontchatbot.pipeline``.

The NER model is heavyweight, so we monkeypatch ``extract_entities`` to drive
the pipeline through every branch deterministically.
"""

from __future__ import annotations

import pytest

from ontchatbot.core import pipeline
from ontchatbot.ner.inference import Entity


def test_greeting_only_short_circuits_without_model(monkeypatch):
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: [])
    out = pipeline.answer("xin chào ạ")
    assert out["greeting"] is True and out["entities"] == []
    assert "Xin chào" in out["reply"]


def test_out_of_domain_when_no_entity(monkeypatch):
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: [])
    out = pipeline.answer("trận bóng tối qua ai thắng")
    assert out["greeting"] is False
    assert "ngoài phạm vi" in out["reply"]


def test_ontology_block_when_entity_recognised(monkeypatch, onto):
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: fake)
    out = pipeline.answer("quy trình bảo lưu")
    assert out["entities"] and out["entities"][0]["iri"] == "QuyTrinh_BaoLuu"
    assert "bảo lưu" in out["reply"].lower()


def test_greeting_plus_entity_returns_block_only(monkeypatch, onto):
    """Minimal-greeting policy: when the user greets *and* asks something, the
    bot answers the question without the greeting prefix."""
    fake = [Entity(surface="phòng đào tạo", tag="PhongBanHanhChinh", start=0, end=3)]
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: fake)
    out = pipeline.answer("xin chào, cho hỏi phòng đào tạo")
    assert out["greeting"] is True   # heuristic still detects the greeting
    assert not out["reply"].startswith("Xin chào")
    assert "đào tạo" in out["reply"].lower()
