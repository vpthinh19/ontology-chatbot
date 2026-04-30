"""HuggingFace ``Dataset`` helpers for token-classification with PhoBERT.

JSONL rows of the form ``{"tokens": [...], "ner_tags": [...]}`` are tokenised
with ``is_split_into_words=True``; sub-word pieces inherit the word-level BIO
label of their parent token, while special tokens receive ``-100`` so they are
ignored by ``CrossEntropyLoss``.
"""

from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from transformers import PreTrainedTokenizerBase

from ..config import MAX_LENGTH
from ..ontology.loader import bio_label_list


def _read_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def label_mappings() -> tuple[list[str], dict[str, int], dict[int, str]]:
    labels = bio_label_list()
    l2i = {l: i for i, l in enumerate(labels)}
    i2l = {i: l for l, i in l2i.items()}
    return labels, l2i, i2l


def load_split(path: Path, l2i: dict[str, int]) -> Dataset:
    rows = _read_jsonl(path)
    tokens = [r["tokens"] for r in rows]
    tags = [[l2i[t] for t in r["ner_tags"]] for r in rows]
    return Dataset.from_dict({"tokens": tokens, "tags": tags})


def make_tokenize_fn(tokenizer: PreTrainedTokenizerBase):
    """Build a batched preprocessing fn that aligns sub-word pieces to word labels."""

    def _fn(batch):
        enc = tokenizer(
            batch["tokens"],
            is_split_into_words=True,
            truncation=True,
            max_length=MAX_LENGTH,
            padding=False,
        )
        labels: list[list[int]] = []
        for i, tag_seq in enumerate(batch["tags"]):
            word_ids = enc.word_ids(batch_index=i)
            prev = None
            row: list[int] = []
            for wid in word_ids:
                if wid is None:
                    row.append(-100)
                elif wid != prev:
                    row.append(tag_seq[wid])
                else:
                    # Continuation sub-word: keep the same label so seqeval scoring
                    # at word-level (post-aggregation) is consistent. The metrics
                    # module discards subword positions via ``-100`` if desired.
                    row.append(tag_seq[wid])
                prev = wid
            labels.append(row)
        enc["labels"] = labels
        return enc

    return _fn
