"""Tests for runtime logging — covering both the setup module and the pipeline
log records that document every stage."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ontchatbot.core import logging_setup, pipeline
from ontchatbot.ner.inference import Entity


@pytest.fixture(autouse=True)
def _reset_logging_state(monkeypatch):
    """Each test gets a clean configurator state and an isolated package logger."""
    monkeypatch.setattr(logging_setup, "_CONFIGURED", False)
    monkeypatch.setattr(logging_setup, "_ACTIVE_LOG_FILE", None)
    pkg = logging.getLogger("ontchatbot")
    saved = list(pkg.handlers)
    pkg.handlers.clear()
    yield
    pkg.handlers.clear()
    pkg.handlers.extend(saved)


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
    assert "[init]" in text
    assert "hello world" in text


def test_pipeline_logs_each_stage(monkeypatch, caplog, onto):
    """Every pipeline stage emits exactly one identifying tag."""
    fake = [Entity(surface="bảo lưu", tag="QuyTrinhHocVu", start=0, end=2)]
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: fake)

    with caplog.at_level(logging.INFO, logger="ontchatbot"):
        out = pipeline.answer("xin chào, em hỏi về bảo lưu")

    assert out["entities"]
    messages = [r.getMessage() for r in caplog.records]
    text = "\n".join(messages)
    for stage in ("[recv]", "[ner]", "[fuzzy]", "[fetch]", "[render]", "[compose]"):
        assert stage in text, f"missing stage tag {stage} in log:\n{text}"


def test_pipeline_logs_rejected_low_confidence(monkeypatch, caplog, onto):
    fake = [Entity(surface="hoàn toàn vô nghĩa xyz",
                   tag="QuyTrinhHocVu", start=0, end=4)]
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: fake)
    with caplog.at_level(logging.INFO, logger="ontchatbot"):
        pipeline.answer("hoàn toàn vô nghĩa xyz")
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "[fuzzy] reject" in text


def test_empty_input_logs_skip(monkeypatch, caplog):
    monkeypatch.setattr(pipeline, "extract_entities", lambda _t: [])
    with caplog.at_level(logging.INFO, logger="ontchatbot"):
        pipeline.answer("")
    assert any("[skip]" in r.getMessage() for r in caplog.records)
