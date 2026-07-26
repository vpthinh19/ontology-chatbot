"""Schema and executable validation for the direct-SPARQL dataset."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rdflib import Graph

from .config import DATASET_PATH
from .model_text import normalize_model_input
from .query_engine import execute_select, validate_select

REQUIRED_FIELDS = {"id", "family_id", "split", "register", "input", "target"}
ALLOWED_SPLITS = {"train", "validation"}
ALLOWED_REGISTERS = {"formal", "neutral", "colloquial", "noisy"}
UNSUPPORTED_TARGET_CHARACTERS = frozenset("_^<@")


class DatasetError(ValueError):
    """The training release violates its declared contract."""


def load_dataset(path: Path = DATASET_PATH) -> list[dict[str, str]]:
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetError(f"line {line_number}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise DatasetError(f"line {line_number}: record must be an object")
        rows.append(row)
    return rows


def validate_dataset(rows: list[dict[str, Any]], graph: Graph) -> dict[str, Any]:
    if not rows:
        raise DatasetError("dataset is empty")

    ids: set[str] = set()
    normalized_inputs: dict[str, str] = {}
    family_splits: dict[str, set[str]] = defaultdict(set)
    family_targets: dict[str, set[str]] = defaultdict(set)
    split_counts: Counter[str] = Counter()
    register_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    empty_result_ids: list[str] = []

    for index, row in enumerate(rows, 1):
        record_id = str(row.get("id", f"line-{index}"))
        if set(row) != REQUIRED_FIELDS:
            raise DatasetError(
                f"{record_id}: fields must be exactly {sorted(REQUIRED_FIELDS)}, got {sorted(row)}"
            )
        if not all(isinstance(row[field], str) and row[field] for field in REQUIRED_FIELDS):
            raise DatasetError(f"{record_id}: every field must be a non-empty string")
        if record_id in ids:
            raise DatasetError(f"duplicate id: {record_id}")
        ids.add(record_id)

        split = row["split"]
        register = row["register"]
        if split not in ALLOWED_SPLITS:
            raise DatasetError(f"{record_id}: invalid split {split}")
        if register not in ALLOWED_REGISTERS:
            raise DatasetError(f"{record_id}: invalid register {register}")

        normalized = normalize_model_input(row["input"]).casefold()
        duplicate = normalized_inputs.get(normalized)
        if duplicate is not None:
            raise DatasetError(f"normalized input duplicates {duplicate}: {record_id}")
        normalized_inputs[normalized] = record_id

        target = row["target"]
        if "\n" in target or "\r" in target or re.search(r"\s{2,}", target):
            raise DatasetError(f"{record_id}: target must be one canonical line")
        unsupported = sorted(set(target) & UNSUPPORTED_TARGET_CHARACTERS)
        if unsupported:
            raise DatasetError(f"{record_id}: tokenizer-unsafe target characters: {unsupported}")
        validate_select(target)
        result = execute_select(graph, target)
        if not result:
            empty_result_ids.append(record_id)

        family = row["family_id"]
        family_splits[family].add(split)
        family_targets[family].add(target)
        split_counts[split] += 1
        register_counts[register] += 1
        target_counts[target] += 1

    leaked = sorted(family for family, splits in family_splits.items() if len(splits) > 1)
    if leaked:
        raise DatasetError(f"families cross splits: {leaked[:10]}")
    inconsistent = sorted(family for family, targets in family_targets.items() if len(targets) > 1)
    if inconsistent:
        raise DatasetError(f"families have multiple targets: {inconsistent[:10]}")

    return {
        "records": len(rows),
        "families": len(family_splits),
        "targets": len(target_counts),
        "split_counts": dict(sorted(split_counts.items())),
        "register_counts": dict(sorted(register_counts.items())),
        "empty_result_ids": empty_result_ids,
    }
