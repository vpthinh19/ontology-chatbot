"""HuggingFace Dataset adapters for token-classification.

JSONL rows of the form ``{"tokens": [...], "ner_tags": [...]}`` are loaded into
a ``datasets.Dataset`` and tokenised through :func:`make_tokenize_fn`.

Sub-word BIO propagation
------------------------
The first sub-word of a word inherits the word's tag verbatim; every
*continuation* sub-word inherits the same tag, but ``B-X`` is rewritten to
``I-X`` so the entity boundary is asserted only once. This convention is what
``seqeval`` expects for entity-level recovery.

Word→sub-word alignment is delegated to :mod:`ontchatbot.ner.encoding`, which
implements it manually because PhoBERT v2 only ships a slow tokenizer.
"""

from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from transformers import PreTrainedTokenizerBase

from ..core.config import MAX_LENGTH
from ..ontology.store import Ontology
from .inference import NerModel


def bio_label_list() -> list[str]:
    """Thin wrapper over :meth:`Ontology.bio_labels` so callers can stay
    schema-agnostic without holding an Ontology instance."""
    return Ontology.get().bio_labels()


def label_mappings() -> tuple[list[str], dict[str, int], dict[int, str]]:
    labels = bio_label_list()
    l2i = {l: i for i, l in enumerate(labels)}
    return labels, l2i, {i: l for l, i in l2i.items()}


def load_split(path: Path, l2i: dict[str, int]) -> Dataset:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return Dataset.from_dict({
        "tokens": [r["tokens"] for r in rows],
        "tags": [[l2i[t] for t in r["ner_tags"]] for r in rows],
    })


def b_to_i_table(l2i: dict[str, int]) -> dict[int, int]:
    """Precomputed ``B-X id → I-X id`` map for sub-word continuation rewriting."""
    return {l2i[l]: l2i["I-" + l[2:]] for l in l2i if l.startswith("B-")}


def project_labels(word_ids: list[int | None], tag_seq: list[int],
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


def make_tokenize_fn(tokenizer: PreTrainedTokenizerBase):
    _, l2i, _ = label_mappings()
    b_to_i = b_to_i_table(l2i)
    encode = NerModel.make_encoder(tokenizer, MAX_LENGTH)

    def _fn(batch):
        ids_b: list[list[int]] = []
        masks_b: list[list[int]] = []
        labels_b: list[list[int]] = []
        for words, tag_seq in zip(batch["tokens"], batch["tags"]):
            ids, wids = encode(list(words))
            labels_b.append(project_labels(wids, list(tag_seq), b_to_i))
            ids_b.append(ids)
            masks_b.append([1] * len(ids))
        return {"input_ids": ids_b, "attention_mask": masks_b, "labels": labels_b}

    return _fn
