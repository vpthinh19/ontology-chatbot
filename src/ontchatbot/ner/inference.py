"""NER inference: text → entity spans.

Loads the fine-tuned PhoBERT once (cached) and exposes :func:`extract_entities`
which decodes the BIO tag sequence into ``(surface, tag)`` spans for the
downstream fuzzy / SPARQL pipeline. Sub-word logits are aggregated to word
level by taking the prediction of the first sub-word piece — the standard BIO
decoding convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

from ..config import MAX_LENGTH, MODEL_DIR
from .preprocessing import clean, segment


@dataclass(frozen=True)
class Entity:
    surface: str
    tag: str
    start: int  # inclusive word index
    end: int    # exclusive word index


@lru_cache(maxsize=1)
def _load():
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    return tok, model


def predict_word_tags(text: str) -> tuple[list[str], list[str]]:
    """Return parallel word-level ``(words, tags)`` lists for ``text``."""
    tok, model = _load()
    words = segment(clean(text))
    if not words:
        return [], []
    enc = tok(words, is_split_into_words=True, truncation=True,
              max_length=MAX_LENGTH, return_tensors="pt")
    word_ids = enc.word_ids(batch_index=0)
    enc = {k: v.to(model.device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits[0]
    pred_ids = logits.argmax(dim=-1).tolist()
    id2lab = model.config.id2label
    tags = ["O"] * len(words)
    seen: set[int] = set()
    for tid, wid in zip(pred_ids, word_ids):
        if wid is None or wid in seen:
            continue
        seen.add(wid)
        tags[wid] = id2lab[tid]
    return words, tags


def decode_bio(words: list[str], tags: list[str]) -> list[Entity]:
    """Decode parallel ``words/tags`` lists into BIO entity spans."""
    out: list[Entity] = []
    i = 0
    while i < len(tags):
        t = tags[i]
        if t.startswith("B-"):
            label = t[2:]
            j = i + 1
            while j < len(tags) and tags[j] == f"I-{label}":
                j += 1
            surface = " ".join(w.replace("_", " ") for w in words[i:j])
            out.append(Entity(surface=surface, tag=label, start=i, end=j))
            i = j
        else:
            i += 1
    return out


def extract_entities(text: str) -> list[Entity]:
    words, tags = predict_word_tags(text)
    return decode_bio(words, tags)
