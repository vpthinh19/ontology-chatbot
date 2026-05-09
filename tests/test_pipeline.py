"""Tests for :class:`Pipeline` — every branch driven by a stub NerModel."""

from __future__ import annotations

import pytest

from ontchatbot.ner_model import Entity
from ontchatbot.pipeline import Pipeline


class _StubNer:
    def __init__(self, entities: list[Entity] | None = None) -> None:
        self._entities = entities or []

    def extract_entities(self, _text: str) -> list[Entity]:
        return list(self._entities)


def _pipeline(entities: list[Entity] | None = None) -> Pipeline:
    return Pipeline(ner=_StubNer(entities or []))


def test_greeting_only_short_circuits_without_model(ontology):
    out = _pipeline([]).answer("xin chào ạ")
    assert out["greeting"] is True and out["entities"] == []
    assert "Xin chào" in out["reply"]


def test_out_of_domain_when_no_entity(ontology):
    out = _pipeline([]).answer("trận bóng tối qua ai thắng")
    assert out["greeting"] is False
    assert "ngoài phạm vi" in out["reply"]


def test_ontology_block_when_entity_recognised(ontology):
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    out = _pipeline(fake).answer("quy trình bảo lưu")
    assert out["entities"]
    assert "QuyTrinh_BaoLuu" in out["entities"][0]["iris"]
    assert "bảo lưu" in out["reply"].lower()


def test_greeting_plus_entity_returns_block_only(ontology):
    """Minimal-greeting policy: blocks override the greeting prefix."""
    fake = [Entity(surface="phòng đào tạo", tag="PhongBanHanhChinh", start=0, end=3)]
    out = _pipeline(fake).answer("xin chào, cho hỏi phòng đào tạo")
    assert out["greeting"] is True
    assert not out["reply"].startswith("Xin chào")
    assert "đào tạo" in out["reply"].lower()
