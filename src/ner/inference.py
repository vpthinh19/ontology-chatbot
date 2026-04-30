"""NER inference: text → entity spans.

Loads the fine-tuned PhoBERT once and exposes a single :func:`extract_entities`
function returning a list of ``(surface, tag)`` pairs for downstream ontology
lookup. Sub-word logits are aggregated to word level by taking the prediction
of the first sub-word piece, which is the standard convention for BIO tagging.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

from ..config import MAX_LENGTH, MODEL_DIR
from ..data.build_dataset import _seg


@dataclass(frozen=True)
class Entity:
    surface: str
    tag: str
    start: int  # word index
    end: int    # exclusive


@lru_cache(maxsize=1)
def _load():
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    return tok, model


def predict_word_tags(text: str) -> tuple[list[str], list[str]]:
    """Return parallel ``(words, tags)`` lists for an input sentence."""
    tok, model = _load()
    words = _seg(text)
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

    tags: list[str] = ["O"] * len(words)
    seen: set[int] = set()
    for tid, wid in zip(pred_ids, word_ids):
        if wid is None or wid in seen:
            continue
        seen.add(wid)
        tags[wid] = id2lab[tid]
    return words, tags


def extract_entities(text: str) -> list[Entity]:
    """Decode BIO tag sequence into contiguous entity spans."""
    words, tags = predict_word_tags(text)
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
