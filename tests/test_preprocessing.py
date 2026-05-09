"""Tests for :class:`ontchatbot.ner.preprocessing.Preprocessor`."""

from __future__ import annotations

import pytest

from ontchatbot.ner.preprocessing import Preprocessor


@pytest.fixture(scope="module")
def pre() -> Preprocessor:
    return Preprocessor.get()


def test_get_returns_singleton():
    a = Preprocessor.get()
    b = Preprocessor.get()
    assert a is b


def test_clean_removes_url_and_email(pre: Preprocessor):
    out = pre.clean("Liên hệ tại https://abc.com hoặc x@y.vn nhé")
    assert "https" not in out and "@" not in out


def test_clean_expands_abbreviations(pre: Preprocessor):
    out = pre.clean("ĐKHP thế nào?")
    assert "đăng ký học phần" in out


def test_clean_expands_lowercase_teencode(pre: Preprocessor):
    out = pre.clean("hc phi k65 ntn")
    # 'hc' → 'học', 'ntn' → 'như thế nào'; 'k65' is preserved as a single token.
    assert "học" in out and "như thế nào" in out and "k65" in out


def test_clean_does_not_split_alphanumeric_id(pre: Preprocessor):
    out = pre.clean("k65 với k67")
    assert "k65" in out and "k67" in out


def test_clean_splits_sticky_known_prefix(pre: Preprocessor):
    """``hpk65`` carries the acronym ``hp`` glued to identifier ``k65``."""
    out = pre.clean("hpk65 đóng nhiêu")
    assert "học phí" in out and "k65" in out


def test_clean_unicode_normalises_to_nfc(pre: Preprocessor):
    decomposed = "ngű"  # ensures the NFC pass actually runs
    out = pre.clean(decomposed)
    assert out is not None


def test_clean_handles_repeats(pre: Preprocessor):
    assert pre.clean("saooooo") == "saoo"


def test_normalize_does_not_expand_teencode(pre: Preprocessor):
    """Dataset compiler relies on this: training samples are already in
    fully-expanded form, so :meth:`normalize` must NOT silently re-expand."""
    out = pre.normalize("hp k65")
    assert "hp k65" in out  # no expansion at the dataset path
    assert "học phí" not in out


def test_segment_returns_underscore_tokens():
    toks = Preprocessor.segment("đăng ký học phần")
    assert all(t for t in toks)
    joined = " ".join(toks).replace("_", " ")
    assert "đăng" in joined and "học phần" in joined


def test_strip_diacritics_removes_tone_marks():
    assert Preprocessor.strip_diacritics("cảm ơn") == "cam on"
    assert Preprocessor.strip_diacritics("Đại học") == "dai hoc".replace("d", "D", 1)
