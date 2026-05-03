"""NER inference: text → entity spans.

Loads the fine-tuned PhoBERT once (cached) and exposes :func:`extract_entities`
which decodes the BIO tag sequence into ``(surface, tag)`` spans for the
downstream fuzzy / SPARQL pipeline.

Word-level prediction is obtained by aggregating sub-word logits with the
"first sub-word wins" rule (the convention paired with the BIO sub-word
propagation used at training time). The manual word→sub-word alignment from
:mod:`ontchatbot.ner.encoding` is reused here so training and inference share
identical pre-processing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

from ..config import MAX_LENGTH, MODEL_DIR
from .encoding import make_word_encoder
from .preprocessing import clean, segment

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    surface: str
    tag: str
    start: int  # inclusive word index
    end: int    # exclusive word index


@lru_cache(maxsize=1)
def _load():
    log.info("[load] loading PhoBERT NER from %s", MODEL_DIR)
    tok = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    model.eval()
    if torch.cuda.is_available():
        model.cuda()
    encode = make_word_encoder(tok, MAX_LENGTH)
    log.info("[load] device=%s n_labels=%d", model.device, len(model.config.id2label))
    return tok, model, encode


def predict_word_tags(text: str) -> tuple[list[str], list[str]]:
    """Return parallel word-level ``(words, tags)`` arrays for ``text``."""
    tok, model, encode = _load()
    cleaned = clean(text)
    log.debug("[preprocess] raw=%r cleaned=%r", text, cleaned)
    words = segment(cleaned)
    log.info("[preprocess] words(n=%d)=%s", len(words), words)
    if not words:
        return [], []

    input_ids, word_ids = encode(words)
    log.debug("[encode] subword_ids(n=%d) word_ids=%s",
              len(input_ids), word_ids)
    ids_t = torch.tensor([input_ids], device=model.device)
    mask_t = torch.ones_like(ids_t)
    with torch.no_grad():
        logits = model(input_ids=ids_t, attention_mask=mask_t).logits[0]
    pred_ids = logits.argmax(dim=-1).tolist()
    id2lab = model.config.id2label

    tags = ["O"] * len(words)
    seen: set[int] = set()
    for tid, wid in zip(pred_ids, word_ids):
        if wid is None or wid in seen:
            continue
        seen.add(wid)
        tags[wid] = id2lab[tid]
    log.info("[ner] tags=%s", list(zip(words, tags)))
    return words, tags


def decode_bio(words: list[str], tags: list[str]) -> list[Entity]:
    """Decode parallel ``words/tags`` arrays into BIO entity spans."""
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
