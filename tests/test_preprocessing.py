"""Tests for ``ontchatbot.ner.preprocessing``."""

from __future__ import annotations

from ontchatbot.ner.preprocessing import clean, segment


def test_clean_removes_url_and_email():
    out = clean("Liên hệ tại https://abc.com hoặc x@y.vn nhé")
    assert "https" not in out and "@" not in out


def test_clean_expands_abbreviations():
    out = clean("ĐKHP thế nào?")
    assert "đăng ký học phần" in out


def test_clean_handles_repeats():
    assert clean("saooooo") == "saoo"


def test_segment_returns_underscore_tokens():
    toks = segment("đăng ký học phần")
    # underthesea joins multi-word units with underscores
    assert all(t for t in toks)
    joined = " ".join(toks).replace("_", " ")
    assert "đăng" in joined and "học phần" in joined
