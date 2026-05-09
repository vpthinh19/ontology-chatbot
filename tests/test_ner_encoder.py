"""Tests for :meth:`NerModel.make_encoder` — the manual word→sub-word aligner."""

from __future__ import annotations

import pytest

from ontchatbot.ner_model import NerModel


class _Stub:
    """Splits each word into single-character tokens; ids are codepoints."""
    cls_token_id = 1
    sep_token_id = 2

    def tokenize(self, word: str) -> list[str]:
        return list(word)

    def convert_tokens_to_ids(self, toks: list[str]) -> list[int]:
        return [ord(t) for t in toks]


def test_encoder_emits_cls_sep_and_word_ids():
    enc = NerModel.make_encoder(_Stub(), max_length=16)
    ids, wids = enc(["ab", "c"])
    assert ids[0] == _Stub.cls_token_id and ids[-1] == _Stub.sep_token_id
    assert wids[0] is None and wids[-1] is None
    assert wids[1:-1] == [0, 0, 1]


def test_encoder_skips_words_that_overflow_budget():
    enc = NerModel.make_encoder(_Stub(), max_length=4)  # cls + 2 subs + sep
    ids, wids = enc(["abc", "d"])
    assert ids[0] == _Stub.cls_token_id and ids[-1] == _Stub.sep_token_id
    assert len([w for w in wids if w is not None]) <= 2


def test_encoder_caches_repeated_words():
    enc = NerModel.make_encoder(_Stub(), max_length=64)
    a, _ = enc(["xin", "chao", "xin", "chao"])
    b, _ = enc(["xin", "chao", "xin", "chao"])
    assert a == b


@pytest.fixture(scope="module")
def phobert():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("vinai/phobert-base-v2")


def test_real_phobert_alignment_round_trip(phobert):
    words = ["Quy_trình", "bảo_lưu", "thế_nào", "?"]
    enc = NerModel.make_encoder(phobert, max_length=32)
    ids, wids = enc(words)
    assert len(ids) == len(wids)
    assert ids[0] == phobert.cls_token_id
    assert ids[-1] == phobert.sep_token_id
    for w in wids[1:-1]:
        assert isinstance(w, int) and 0 <= w < len(words)
    assert {w for w in wids if w is not None} == set(range(len(words)))
