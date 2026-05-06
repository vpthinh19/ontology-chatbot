"""Tests for the chain-of-stages pipeline architecture."""

from __future__ import annotations

import pytest

from ontchatbot.core import pipeline
from ontchatbot.core.pipeline import (
    DEFAULT_STAGES,
    Pipeline,
    PipelineContext,
    compose_stage,
    fuzzy_stage,
    greeting_stage,
    ner_stage,
    render_stage,
    trim_stage,
)
from ontchatbot.ner.inference import Entity


def test_default_stage_order_is_canonical():
    expected = (trim_stage, greeting_stage, ner_stage,
                fuzzy_stage, render_stage, compose_stage)
    assert tuple(DEFAULT_STAGES) == expected


def test_trim_stage_records_text():
    ctx = trim_stage(PipelineContext(query="  hello  "))
    assert ctx.text == "hello"


def test_greeting_stage_detects_diacritic_loss():
    ctx = PipelineContext(query="cam on", text="cam on")
    out = greeting_stage(ctx)
    assert out.greeting is True


def test_pipeline_runs_all_stages_in_order(monkeypatch, onto):
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: fake)
    out = pipeline.answer("xin chào, em hỏi về bảo lưu")
    assert out["greeting"] is True
    assert out["entities"][0]["iri"] == "QuyTrinh_BaoLuu"
    assert out["reply"].startswith("Xin chào")


def test_custom_pipeline_can_swap_stages(monkeypatch, onto):
    """A research extension should be able to drop in a different NER backend."""
    fake_spans = [Entity(surface="phòng đào tạo",
                         tag="PhongBanHanhChinh", start=0, end=3)]

    def stub_ner(ctx: PipelineContext) -> PipelineContext:
        ctx.spans = list(fake_spans)
        return ctx

    custom = Pipeline(stages=(trim_stage, greeting_stage, stub_ner,
                              fuzzy_stage, render_stage, compose_stage))
    out = custom.run("phòng đào tạo")
    assert out["entities"] and out["entities"][0]["iri"] == "PhongDaoTaoDaiHoc"


def test_empty_query_short_circuits_to_greeting(monkeypatch):
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: [])
    out = pipeline.answer("   ")
    assert out["greeting"] is True
    assert out["entities"] == []
    assert "Xin chào" in out["reply"]
