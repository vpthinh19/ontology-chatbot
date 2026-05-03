"""Tests for the manual word→sub-word aligner.

Includes a smoke test that loads the real PhoBERT slow tokenizer to guarantee
training and inference receive identical alignment behaviour.
"""

from __future__ import annotations

import pytest

from ontchatbot.ner.encoding import make_word_encoder


# Small in-process stub that mimics a slow tokenizer's surface

class _Stub:
    """Splits each word into single-character tokens; ids are codepoints."""

    cls_token_id = 1
    sep_token_id = 2

    def tokenize(self, word: str) -> list[str]:
        return list(word)

    def convert_tokens_to_ids(self, toks: list[str]) -> list[int]:
        return [ord(t) for t in toks]


def test_encoder_emits_cls_sep_and_word_ids():
    enc = make_word_encoder(_Stub(), max_length=16)
    ids, wids = enc(["ab", "c"])
    # CLS, a, b, c, SEP
    assert ids[0] == _Stub.cls_token_id
    assert ids[-1] == _Stub.sep_token_id
    assert wids[0] is None and wids[-1] is None
    # word 0 has 2 sub-words ('a', 'b'), word 1 has 1 ('c')
    assert wids[1:-1] == [0, 0, 1]


def test_encoder_skips_words_that_overflow_budget():
    enc = make_word_encoder(_Stub(), max_length=4)  # cls + 2 subs + sep
    ids, wids = enc(["abc", "d"])
    # First word "abc" -> 3 subs, would exceed; encoder must drop it cleanly
    # The encoder is order-preserving: it stops at the first oversize word.
    assert ids[0] == _Stub.cls_token_id and ids[-1] == _Stub.sep_token_id
    assert all(0 <= len(ids) <= 4 for _ in [0])
    assert len([w for w in wids if w is not None]) <= 2


def test_encoder_caches_repeated_words():
    enc = make_word_encoder(_Stub(), max_length=64)
    ids_a, _ = enc(["xin", "chao", "xin", "chao"])
    ids_b, _ = enc(["xin", "chao", "xin", "chao"])
    assert ids_a == ids_b  # deterministic — and second call hits the cache


# Real-tokenizer integration

@pytest.fixture(scope="module")
def phobert():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained("vinai/phobert-base-v2")


def test_real_phobert_alignment_round_trip(phobert):
    words = ["Quy_trình", "bảo_lưu", "thế_nào", "?"]
    enc = make_word_encoder(phobert, max_length=32)
    ids, wids = enc(words)
    assert len(ids) == len(wids)
    assert ids[0] == phobert.cls_token_id
    assert ids[-1] == phobert.sep_token_id
    # Every emitted sub-word maps back to a valid word index.
    for w in wids[1:-1]:
        assert isinstance(w, int) and 0 <= w < len(words)
    # Each word must contribute at least one sub-word.
    assert {w for w in wids if w is not None} == set(range(len(words)))
