"""Neural NER: text → entity spans.

The :class:`NerModel` owns *every* model-related concern:

* lazy load of the fine-tuned PhoBERT tokenizer + token-classification head
  (singleton via :meth:`NerModel.get`);
* the manual word→sub-word aligner used by both training and inference
  (exposed as the static method :meth:`make_encoder` so the dataset
  compiler can call it without instantiating a heavyweight model);
* word-level prediction with the canonical "first sub-word wins"
  aggregation; and
* lenient BIO span decoding that recovers entities even when the model
  emits ``I-X`` without a leading ``B-X``.

Why a manual word→sub-word aligner?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
PhoBERT v2 ships only a slow (Python) tokenizer, so
``BatchEncoding.word_ids()`` is unavailable. We therefore tokenise each
word independently, concatenate the resulting sub-word ids with the
``<s>``/``</s>`` markers, and record the originating word index of every
emitted sub-word in a parallel ``word_ids`` array. Downstream code uses
that array exactly like a fast-tokenizer ``word_ids()`` would have.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import torch
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    PreTrainedTokenizerBase,
)

from ..core.config import MAX_LENGTH, MODEL_DIR
from .preprocessing import Preprocessor

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    """One BIO-decoded span returned to callers."""
    surface: str
    tag: str
    start: int  # inclusive word index
    end: int    # exclusive word index


class NerModel:
    """Process-level NER backbone; singleton via ``get()``."""

    def __init__(self,
                 model_dir=MODEL_DIR,
                 max_length: int = MAX_LENGTH,
                 preprocessor: Preprocessor | None = None) -> None:
        self._model_dir = str(model_dir)
        self._max_length = int(max_length)
        self._pre = preprocessor or Preprocessor.get()
        self._tok = None
        self._model = None
        self._encode = None

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "NerModel":
        return cls()

    # Public API

    def extract_entities(self, text: str) -> list[Entity]:
        """text → list of BIO-decoded :class:`Entity` spans."""
        words, tags = self._predict_word_tags(text)
        return self.decode_bio(words, tags)

    @staticmethod
    def decode_bio(words: list[str], tags: list[str]) -> list[Entity]:
        """Decode parallel ``words/tags`` arrays into BIO entity spans.

        *Lenient* decoding: an ``I-X`` tag preceded by ``O`` or by a
        different label still opens a new entity. This recovers spans the
        model emits without a leading ``B-X`` — a common failure mode when
        multiple entities of the same class appear close together
        (e.g. *"hp k65 và k67"*).
        """
        out: list[Entity] = []
        i = 0
        n = len(tags)
        while i < n:
            t = tags[i]
            if t == "O":
                i += 1
                continue
            label = t[2:]
            j = i + 1
            while j < n and tags[j] == f"I-{label}":
                j += 1
            surface = " ".join(w.replace("_", " ") for w in words[i:j])
            out.append(Entity(surface=surface, tag=label, start=i, end=j))
            i = j
        return out

    @staticmethod
    def make_encoder(
        tokenizer: PreTrainedTokenizerBase,
        max_length: int,
    ) -> Callable[[list[str]], tuple[list[int], list[int | None]]]:
        """Return a closure ``encode(words) -> (input_ids, word_ids)``.

        Training (``dataset.py``) and inference (this class) both call this
        — keeping the implementation here ensures both code paths use
        identical word→sub-word alignment, so a span tagged at training
        time is restored exactly at inference time.

        The closure includes ``<s>``/``</s>`` and respects ``max_length`` by
        dropping any word whose sub-words would not all fit before ``</s>``.
        Per-word sub-word ids are memoised; conversational Vietnamese has a
        long tail of high-frequency function words, so cache hit rate is
        high and Python tokenisation cost is amortised.
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

    # Internals

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        log.info("[NerModel] loading PhoBERT NER from %s", self._model_dir)
        self._tok = AutoTokenizer.from_pretrained(self._model_dir)
        self._model = AutoModelForTokenClassification.from_pretrained(self._model_dir)
        self._model.eval()
        if torch.cuda.is_available():
            self._model.cuda()
        self._encode = NerModel.make_encoder(self._tok, self._max_length)
        log.info("[NerModel] device=%s n_labels=%d",
                 self._model.device, len(self._model.config.id2label))

    def _predict_word_tags(self, text: str) -> tuple[list[str], list[str]]:
        """Return parallel word-level ``(words, tags)`` arrays."""
        self._ensure_loaded()
        cleaned = self._pre.clean(text)
        log.debug("[NerModel] cleaned=%r", cleaned)
        words = Preprocessor.segment(cleaned)
        log.info("[NerModel] words(n=%d)=%s", len(words), words)
        if not words:
            return [], []

        input_ids, word_ids = self._encode(words)
        ids_t = torch.tensor([input_ids], device=self._model.device)
        mask_t = torch.ones_like(ids_t)
        with torch.no_grad():
            logits = self._model(input_ids=ids_t, attention_mask=mask_t).logits[0]
        pred_ids = logits.argmax(dim=-1).tolist()
        id2lab = self._model.config.id2label

        tags = ["O"] * len(words)
        seen: set[int] = set()
        for tid, wid in zip(pred_ids, word_ids):
            if wid is None or wid in seen:
                continue
            seen.add(wid)
            tags[wid] = id2lab[tid]
        log.info("[NerModel] tags=%s", list(zip(words, tags)))
        return words, tags
