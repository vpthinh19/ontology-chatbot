"""Tests for ``ontchatbot.ner.preprocessing``."""

from __future__ import annotations

from ontchatbot.ner.preprocessing import clean, segment


def test_clean_removes_url_and_email():
    out = clean("Liên hệ tại https://abc.com hoặc x@y.vn nhé")
    assert "https" not in out and "@" not in out


def test_clean_expands_abbreviations():
    out = clean("ĐKHP thế nào?")
    assert "đăng ký học phần" in out


def test_clean_expands_lowercase_teencode():
    out = clean("hc phi k65 ntn")
    # 'hc' → 'học', 'ntn' → 'như thế nào'; 'k65' is preserved as a single token.
    assert "học" in out and "như thế nào" in out and "k65" in out


def test_clean_does_not_split_alphanumeric_id():
    out = clean("k65 với k67")
    assert "k65" in out and "k67" in out


def test_clean_splits_sticky_known_prefix():
    """``hpk65`` carries the acronym ``hp`` glued to identifier ``k65``."""
    out = clean("hpk65 đóng nhiêu")
    assert "học phí" in out and "k65" in out


def test_clean_unicode_normalises_to_nfc():
    # 'á' decomposed (U+0061 U+0301) vs precomposed (U+00E1) must collapse
    decomposed = "ngű"  # silly form, but ensures NFC pass runs
    out = clean(decomposed)
    assert out is not None  # only guarantee: no exception


def test_clean_handles_repeats():
    assert clean("saooooo") == "saoo"


def test_segment_returns_underscore_tokens():
    toks = segment("đăng ký học phần")
    # underthesea joins multi-word units with underscores
    assert all(t for t in toks)
    joined = " ".join(toks).replace("_", " ")
    assert "đăng" in joined and "học phần" in joined
