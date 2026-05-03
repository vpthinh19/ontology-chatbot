"""HuggingFace Dataset adapters for token-classification.

JSONL rows of the form ``{"tokens": [...], "ner_tags": [...]}`` are loaded into
a ``datasets.Dataset`` and tokenised with ``is_split_into_words=True``.

Sub-word BIO propagation rule: the *first* sub-word of a word inherits the
word's tag verbatim; every *continuation* sub-word inherits the same tag, but
``B-X`` is rewritten to ``I-X`` so the entity boundary is asserted only once.
This is the standard convention recommended by HuggingFace tutorials and
required for ``seqeval`` to recover the original entity span at evaluation.
"""

from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from transformers import PreTrainedTokenizerBase

from ..config import MAX_LENGTH
from ..ontology.loader import bio_label_list


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


def _b_to_i_table(l2i: dict[str, int]) -> dict[int, int]:
    """Precomputed ``B-X id → I-X id`` map for sub-word continuation rewriting."""
    return {l2i[l]: l2i["I-" + l[2:]] for l in l2i if l.startswith("B-")}


def make_tokenize_fn(tokenizer: PreTrainedTokenizerBase):
    _, l2i, _ = label_mappings()
    b_to_i = _b_to_i_table(l2i)

    def _fn(batch):
        enc = tokenizer(
            batch["tokens"],
            is_split_into_words=True,
            truncation=True,
            max_length=MAX_LENGTH,
            padding=False,
        )
        out: list[list[int]] = []
        for i, tag_seq in enumerate(batch["tags"]):
            row: list[int] = []
            prev: int | None = None
            for wid in enc.word_ids(batch_index=i):
                if wid is None:
                    row.append(-100)
                elif wid != prev:
                    row.append(tag_seq[wid])
                else:
                    # Continuation sub-word: keep the entity but downgrade B→I.
                    row.append(b_to_i.get(tag_seq[wid], tag_seq[wid]))
                prev = wid
            out.append(row)
        enc["labels"] = out
        return enc

    return _fn
