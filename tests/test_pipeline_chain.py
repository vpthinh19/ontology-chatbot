"""Tests for the OOP :class:`Pipeline` chain.

These exercise the threading of :class:`PipelineContext` through the
methods of :class:`Pipeline`, plus the swap-ability of injected
collaborators (the whole point of the composition design).
"""

from __future__ import annotations

import asyncio

import pytest

from ontchatbot.core.pipeline import Pipeline, PipelineContext
from ontchatbot.ner.inference import Entity


class _StubNer:
    def __init__(self, entities: list[Entity] | None = None) -> None:
        self._entities = entities or []

    def extract_entities(self, _t: str) -> list[Entity]:
        return list(self._entities)


def test_preprocess_records_text_and_greeting():
    p = Pipeline(ner=_StubNer())
    ctx = p._preprocess(PipelineContext(query="  cam on  "))
    assert ctx.text == "cam on"
    assert ctx.greeting is True


def test_preprocess_handles_empty():
    p = Pipeline(ner=_StubNer())
    ctx = p._preprocess(PipelineContext(query=""))
    assert ctx.text == ""
    assert ctx.greeting is False


def test_pipeline_runs_all_stages_in_order(ontology):
    """End-to-end: preprocess → ner → match → query → present."""
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    out = Pipeline(ner=_StubNer(fake)).answer("xin chào, em hỏi về bảo lưu")
    assert out["greeting"] is True
    assert out["entities"][0]["tag"] == "QuyTrinhHocVu"
    assert "QuyTrinh_BaoLuu" in out["entities"][0]["iris"]
    # Minimal-greeting policy
    assert not out["reply"].startswith("Xin chào")
    assert "bảo lưu" in out["reply"].lower()


def test_custom_pipeline_swaps_ner_via_constructor(ontology):
    """A research extension drops in a different NER backend by handing a
    duck-typed object to the Pipeline constructor — no global patching."""
    fake = [Entity(surface="phòng đào tạo",
                   tag="PhongBanHanhChinh", start=0, end=3)]
    out = Pipeline(ner=_StubNer(fake)).answer("phòng đào tạo")
    assert out["entities"]
    assert "PhongDaoTaoDaiHoc" in out["entities"][0]["iris"]


def test_empty_query_short_circuits_to_greeting(ontology):
    out = Pipeline(ner=_StubNer()).answer("   ")
    assert out["greeting"] is True
    assert out["entities"] == []
    assert "Xin chào" in out["reply"]


def test_class_level_query_renders_listing(ontology):
    """Class-level question routes to the listing template."""
    fake = [Entity(surface="quy trình học vụ",
                   tag="QuyTrinhHocVu", start=0, end=3)]
    out = Pipeline(ner=_StubNer(fake)).answer(
        "trường mình có những quy trình học vụ nào")
    assert out["entities"][0]["class_won"] is True
    assert "Quy trình xin bảo lưu" in out["reply"]
    assert "Quy trình đóng học phí" in out["reply"]


def test_multi_match_renders_every_individual(ontology):
    """``"k65"`` resolves to multiple fees — every above-threshold IRI
    is rendered, fixing the historical top-1 collapse."""
    fake = [Entity(surface="k65", tag="DinhMucHocPhi", start=0, end=1)]
    out = Pipeline(ner=_StubNer(fake)).answer("học phí k65 thế nào")
    assert out["entities"][0]["class_won"] is False
    iris = set(out["entities"][0]["iris"])
    assert {"Phi_K65_550k", "Phi_K65_620k"} <= iris
    assert "550,000" in out["reply"] and "620,000" in out["reply"]


def test_async_aanswer_returns_same_payload(ontology):
    """The async wrapper produces the same dict as the sync entry."""
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    pipeline = Pipeline(ner=_StubNer(fake))
    sync_out = pipeline.answer("bảo lưu")
    async_out = asyncio.run(pipeline.aanswer("bảo lưu"))
    assert sync_out == async_out
