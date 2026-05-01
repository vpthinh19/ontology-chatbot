"""HuggingFace Dataset adapters for token-classification.

JSONL rows of the form ``{"tokens": [...], "ner_tags": [...]}`` are loaded into
a ``datasets.Dataset`` and tokenised with ``is_split_into_words=True``. Word
labels are propagated to every sub-word piece so that the standard
``CrossEntropyLoss`` over flattened sub-words matches the NER objective.
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


def make_tokenize_fn(tokenizer: PreTrainedTokenizerBase):
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
            row: list[int] = []
            for wid in enc.word_ids(batch_index=i):
                row.append(-100 if wid is None else tag_seq[wid])
            labels.append(row)
        enc["labels"] = labels
        return enc

    return _fn
