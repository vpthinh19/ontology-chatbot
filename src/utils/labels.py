"""Label utilities for single-label and multi-label datasets."""

from __future__ import annotations

import json
from collections.abc import Iterable

from sklearn.preprocessing import MultiLabelBinarizer


def load_label_names(label_map_path: str) -> list[str]:
    """Load ordered label names from label_map.json."""
    with open(label_map_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [next(iter(entry)) for entry in raw]


def build_mlb(label_names: list[str]) -> MultiLabelBinarizer:
    """Build a MultiLabelBinarizer with fixed label order."""
    mlb = MultiLabelBinarizer(classes=label_names)
    mlb.fit([label_names])
    return mlb


def extract_sample_labels(sample: dict) -> list[str]:
    """Extract a list of labels from a dataset sample.

    Supports both legacy single-label datasets and the current entity-based format.
    """
    if "entities" in sample and sample["entities"] is not None:
        entities = sample["entities"]
        if isinstance(entities, list):
            labels: list[str] = []
            for entity in entities:
                if isinstance(entity, dict):
                    label = entity.get("label")
                    if isinstance(label, str) and label:
                        labels.append(label)
            return sorted(set(labels))

    label = sample.get("label")
    if isinstance(label, str) and label:
        return [label]

    labels = sample.get("labels")
    if isinstance(labels, list):
        return [str(lbl) for lbl in labels if isinstance(lbl, str) and lbl]

    return []


def encode_multi_labels(label_names: list[str], sample: dict) -> list[int]:
    """Encode a sample into a multi-hot label vector."""
    label_set = set(extract_sample_labels(sample))
    return [1 if label in label_set else 0 for label in label_names]
