"""Manual word→sub-word aligner for the *slow* PhoBERT tokenizer.

PhoBERT v2 ships only a slow (Python) tokenizer, which means
``BatchEncoding.word_ids()`` is unavailable. We therefore implement the
alignment by hand: each input word is tokenised independently, the resulting
sub-word ids are concatenated with the special ``<s>``/``</s>`` markers, and
a parallel ``word_ids`` array records the originating word index of every
emitted sub-word (``None`` for special tokens). Downstream code uses this
array exactly like the fast-tokenizer ``word_ids()`` would have provided.

Speed
-----
Python-level per-word tokenisation is the natural bottleneck for slow
tokenizers. We mitigate it by memoising every word's sub-word id sequence in
an ``lru_cache`` keyed on the encoder + word — Vietnamese conversational data
contains many high-frequency function words, so cache hit rate is high.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from transformers import PreTrainedTokenizerBase


def make_word_encoder(
    tokenizer: PreTrainedTokenizerBase,
    max_length: int,
) -> Callable[[list[str]], tuple[list[int], list[int | None]]]:
    """Return a closure ``encode(words) -> (input_ids, word_ids)``.

    The closure includes ``<s>``/``</s>`` and respects ``max_length`` by
    dropping any word whose sub-words would not all fit before ``</s>``.
    """
    cls_id = tokenizer.cls_token_id
    sep_id = tokenizer.sep_token_id
    convert = tokenizer.convert_tokens_to_ids
    tokenize = tokenizer.tokenize

    @lru_cache(maxsize=8192)
    def _word_to_ids(word: str) -> tuple[int, ...]:
        return tuple(convert(tokenize(word)))

    def encode(words: list[str]) -> tuple[list[int], list[int | None]]:
        ids: list[int] = [cls_id]
        wids: list[int | None] = [None]
        budget = max_length - 1  # leave room for </s>
        for w_idx, w in enumerate(words):
            sub = _word_to_ids(w)
            if not sub:
                continue
            if len(ids) + len(sub) > budget:
                break
            ids.extend(sub)
            wids.extend([w_idx] * len(sub))
        ids.append(sep_id)
        wids.append(None)
        return ids, wids

    return encode
