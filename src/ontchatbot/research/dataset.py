"""Loading and executable validation for the canonical dataset."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from rdflib import Graph

from ..runtime.sparql import execute_select, validate_select
from ..runtime.text import normalize_model_input
from ..settings import DATASET_DIR

REQUIRED_FIELDS = {"id", "family_id", "register", "query_shape", "input", "target"}
REQUIRED_SPLITS = ("train", "val", "test")
ALLOWED_REGISTERS = {"formal", "neutral", "colloquial", "noisy"}
ALLOWED_QUERY_SHAPES = {
    "direct",
    "graph_hop",
    "multi_column",
    "aggregate",
    "aggregate_filter",
}
UNSUPPORTED_TARGET_CHARACTERS = frozenset("_^<@")


class DatasetError(ValueError):
    """The dataset violates its declared contract."""


def load_dataset(path: Path) -> list[dict[str, str]]:
    """Load one JSON Lines split."""

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


def load_release(directory: Path = DATASET_DIR) -> dict[str, list[dict[str, str]]]:
    """Load the three standard dataset files."""

    directory = Path(directory)
    return {split: load_dataset(directory / f"{split}.jsonl") for split in REQUIRED_SPLITS}


def validate_dataset(rows: list[dict[str, Any]], graph: Graph) -> dict[str, Any]:
    """Validate one split without relying on a field that duplicates its filename."""

    if not rows:
        raise DatasetError("dataset split is empty")

    ids: set[str] = set()
    normalized_inputs: dict[str, str] = {}
    family_targets: dict[str, set[str]] = defaultdict(set)
    register_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
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

        register = row["register"]
        shape = row["query_shape"]
        if register not in ALLOWED_REGISTERS:
            raise DatasetError(f"{record_id}: invalid register {register}")
        if shape not in ALLOWED_QUERY_SHAPES:
            raise DatasetError(f"{record_id}: invalid query shape {shape}")

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
        if not execute_select(graph, target):
            empty_result_ids.append(record_id)

        family_targets[row["family_id"]].add(target)
        register_counts[register] += 1
        shape_counts[shape] += 1
        target_counts[target] += 1

    inconsistent = sorted(family for family, targets in family_targets.items() if len(targets) > 1)
    if inconsistent:
        raise DatasetError(f"families have multiple targets: {inconsistent[:10]}")

    return {
        "records": len(rows),
        "families": len(family_targets),
        "targets": len(target_counts),
        "register_counts": dict(sorted(register_counts.items())),
        "query_shape_counts": dict(sorted(shape_counts.items())),
        "empty_result_ids": empty_result_ids,
    }


def validate_release(
    splits: dict[str, list[dict[str, Any]]],
    graph: Graph,
) -> dict[str, Any]:
    """Validate all files and reject leakage between splits."""

    if set(splits) != set(REQUIRED_SPLITS):
        raise DatasetError(f"release must contain exactly {list(REQUIRED_SPLITS)}")

    reports = {name: validate_dataset(rows, graph) for name, rows in splits.items()}
    family_locations: dict[str, set[str]] = defaultdict(set)
    question_locations: dict[str, set[str]] = defaultdict(set)
    id_locations: dict[str, set[str]] = defaultdict(set)
    for split, rows in splits.items():
        for row in rows:
            family_locations[row["family_id"]].add(split)
            question_locations[normalize_model_input(row["input"]).casefold()].add(split)
            id_locations[row["id"]].add(split)

    for label, locations in (
        ("families", family_locations),
        ("questions", question_locations),
        ("ids", id_locations),
    ):
        leaked = sorted(key for key, values in locations.items() if len(values) > 1)
        if leaked:
            raise DatasetError(f"{label} cross splits: {leaked[:10]}")

    return {
        "records": sum(report["records"] for report in reports.values()),
        "split_counts": {name: reports[name]["records"] for name in REQUIRED_SPLITS},
        "splits": reports,
    }
