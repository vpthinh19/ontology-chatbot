"""NerModel: PhoBERT NER inference + training-data utilities."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

import torch
from datasets import Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    PreTrainedTokenizerBase,
)

from .config import MAX_LENGTH, MODEL_DIR
from .ontology import Ontology
from .preprocessor import Preprocessor

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    """One BIO-decoded span."""
    surface: str
    tag: str
    start: int  # inclusive word index
    end: int    # exclusive word index


class NerModel:
    """PhoBERT NER backbone + training adapters; singleton via ``get()``."""

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

    # Inference

    def extract_entities(self, text: str) -> list[Entity]:
        """text → list of BIO-decoded :class:`Entity` spans."""
        words, tags = self._predict_word_tags(text)
        return self.decode_bio(words, tags)

    @staticmethod
    def decode_bio(words: list[str], tags: list[str]) -> list[Entity]:
        """Decode parallel word/tag arrays into BIO entity spans.

        Lenient: an ``I-X`` after ``O`` opens a new entity, recovering spans
        the model emits without a leading ``B-X`` (common when two same-class
        entities are adjacent, e.g. *"hp k65 và k67"*).
        """
        out: list[Entity] = []
        i, n = 0, len(tags)
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

    # Schema (BIO labels)

    @staticmethod
    def bio_labels(tags: list[str] | None = None) -> list[str]:
        """Project NER tags into ``[O, B-X, I-X, ...]`` BIO format."""
        if tags is None:
            tags = Ontology.get().tags
        out = ["O"]
        for tag in tags:
            out.extend([f"B-{tag}", f"I-{tag}"])
        return out

    @staticmethod
    def label_mappings() -> tuple[list[str], dict[str, int], dict[int, str]]:
        labels = NerModel.bio_labels()
        l2i = {l: i for i, l in enumerate(labels)}
        return labels, l2i, {i: l for l, i in l2i.items()}

    # Word→sub-word aligner (used by both inference and training)

    @staticmethod
    def make_encoder(
        tokenizer: PreTrainedTokenizerBase,
        max_length: int,
    ) -> Callable[[list[str]], tuple[list[int], list[int | None]]]:
        """Manual word→sub-word aligner; same closure used by training and inference.

        PhoBERT v2 ships only a slow tokenizer (no ``BatchEncoding.word_ids``),
        so the alignment is built manually so a span tagged at training time
        decodes exactly at inference time.
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

    # Training-time data adapters (formerly dataset.py)

    @staticmethod
    def b_to_i_table(l2i: dict[str, int]) -> dict[int, int]:
        """``B-X id → I-X id`` map for sub-word continuation rewriting."""
        return {l2i[l]: l2i["I-" + l[2:]] for l in l2i if l.startswith("B-")}

    @staticmethod
    def project_labels(word_ids: list[int | None],
                       tag_seq: list[int],
                       b_to_i: dict[int, int]) -> list[int]:
        """Map word-level tags onto a sub-word sequence with B→I downgrade."""
        out: list[int] = []
        prev: int | None = None
        for wid in word_ids:
            if wid is None:
                out.append(-100)
            elif wid != prev:
                out.append(tag_seq[wid])
            else:
                t = tag_seq[wid]
                out.append(b_to_i.get(t, t))
            prev = wid
        return out

    @staticmethod
    def make_tokenize_fn(tokenizer: PreTrainedTokenizerBase):
        """HuggingFace ``Dataset.map`` callable: word-level → sub-word features."""
        _, l2i, _ = NerModel.label_mappings()
        b_to_i = NerModel.b_to_i_table(l2i)
        encode = NerModel.make_encoder(tokenizer, MAX_LENGTH)

        def _fn(batch):
            ids_b, masks_b, labels_b = [], [], []
            for words, tag_seq in zip(batch["tokens"], batch["tags"]):
                ids, wids = encode(list(words))
                labels_b.append(NerModel.project_labels(wids, list(tag_seq), b_to_i))
                ids_b.append(ids)
                masks_b.append([1] * len(ids))
            return {"input_ids": ids_b, "attention_mask": masks_b, "labels": labels_b}
        return _fn

    @staticmethod
    def load_split(path: Path, l2i: dict[str, int]) -> Dataset:
        """JSONL → HuggingFace ``Dataset`` with ``tokens`` and ``tags`` columns."""
        rows: list[dict] = []
        with Path(path).open("r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return Dataset.from_dict({
            "tokens": [r["tokens"] for r in rows],
            "tags": [[l2i[t] for t in r["ner_tags"]] for r in rows],
        })

    # Internals — inference path

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
        """Word-level ``(words, tags)`` arrays from a clean-then-segment pass."""
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
