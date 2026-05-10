"""Tests for runtime logging — setup module + per-stage pipeline records."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ontchatbot import logging_setup
from ontchatbot.ner_model import Entity
from ontchatbot.pipeline import Pipeline


@pytest.fixture(autouse=True)
def _reset_logging_state(monkeypatch):
    monkeypatch.setattr(logging_setup, "_CONFIGURED", False)
    monkeypatch.setattr(logging_setup, "_ACTIVE_LOG_FILE", None)
    pkg = logging.getLogger("ontchatbot")
    saved = list(pkg.handlers)
    pkg.handlers.clear()
    yield
    pkg.handlers.clear()
    pkg.handlers.extend(saved)


class _StubNer:
    def __init__(self, entities=None):
        self._entities = entities or []

    def extract_entities(self, _t):
        return list(self._entities)


def test_configure_logging_is_idempotent(tmp_path: Path):
    log_file = tmp_path / "first.log"
    p1 = logging_setup.configure_logging(log_file=log_file, console=False)
    p2 = logging_setup.configure_logging(log_file=tmp_path / "second.log",
                                         console=False)
    assert p1 == log_file and p2 == log_file
    pkg = logging.getLogger("ontchatbot")
    file_handlers = [h for h in pkg.handlers
                     if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1


def test_configure_logging_writes_init_record(tmp_path: Path):
    log_file = tmp_path / "out.log"
    logging_setup.configure_logging(log_file=log_file, console=False)
    logging.getLogger("ontchatbot").info("hello world")
    for h in logging.getLogger("ontchatbot").handlers:
        h.flush()
    text = log_file.read_text(encoding="utf-8")
    assert "[init]" in text and "hello world" in text


def test_pipeline_logs_each_stage(caplog, ontology):
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    pipeline = Pipeline(ner=_StubNer(fake))
    with caplog.at_level(logging.INFO, logger="ontchatbot"):
        out = pipeline.answer("xin chào, em hỏi về bảo lưu")
    assert out["entities"]
    text = "\n".join(r.getMessage() for r in caplog.records)
    for stage in ("[Pipeline.intent]", "[Pipeline.ner]",
                  "[Pipeline.match]", "[Pipeline.query]",
                  "[Pipeline.present]"):
        assert stage in text, f"missing stage tag {stage!r} in log:\n{text}"


def test_pipeline_logs_rejected_low_confidence(caplog, ontology):
    fake = [Entity(surface="hoàn toàn vô nghĩa xyz",
                   tag="QuyTrinhHocVu", start=0, end=4)]
    pipeline = Pipeline(ner=_StubNer(fake))
    with caplog.at_level(logging.INFO, logger="ontchatbot"):
        pipeline.answer("hoàn toàn vô nghĩa xyz")
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[Ontology.resolve]" in text and "reject" in text


def test_empty_input_logs_skip(caplog, ontology):
    pipeline = Pipeline(ner=_StubNer())
    with caplog.at_level(logging.INFO, logger="ontchatbot"):
        pipeline.answer("")
    assert any("[Pipeline]" in r.getMessage() and "skip" in r.getMessage()
               for r in caplog.records)


def test_per_module_logger_is_independent():
    """Per-module loggers tune levels independently via the package hierarchy."""
    intermediate = logging.getLogger("ontchatbot")
    child = logging.getLogger("ontchatbot.ontology")
    sibling = logging.getLogger("ontchatbot.preprocessor")
    assert child.parent is intermediate
    child.setLevel(logging.DEBUG)
    try:
        assert child.getEffectiveLevel() == logging.DEBUG
        assert sibling.getEffectiveLevel() != logging.DEBUG
    finally:
        child.setLevel(logging.NOTSET)
