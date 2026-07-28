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

REQUIRED_FIELDS = {"id", "query_id", "register", "input", "target"}
REQUIRED_SPLITS = ("train", "val", "test")
ALLOWED_REGISTERS = {"formal", "neutral", "colloquial", "noisy"}
REGISTER_ORDER = ("formal", "neutral", "colloquial", "noisy")
UNSUPPORTED_TARGET_CHARACTERS = frozenset("_^<@")
NEAR_DUPLICATE_THRESHOLD = 0.84


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
    query_targets: dict[str, set[str]] = defaultdict(set)
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

        register = row["register"]
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
        if not execute_select(graph, target):
            empty_result_ids.append(record_id)

        query_targets[row["query_id"]].add(target)
        register_counts[register] += 1
        target_counts[target] += 1

    inconsistent = sorted(
        query_id for query_id, targets in query_targets.items() if len(targets) > 1
    )
    if inconsistent:
        raise DatasetError(f"query IDs have multiple targets: {inconsistent[:10]}")

    return {
        "records": len(rows),
        "queries": len(query_targets),
        "targets": len(target_counts),
        "register_counts": dict(sorted(register_counts.items())),
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
    query_targets: dict[str, set[str]] = defaultdict(set)
    target_queries: dict[str, set[str]] = defaultdict(set)
    query_counts = {split: Counter() for split in REQUIRED_SPLITS}
    question_locations: dict[str, set[str]] = defaultdict(set)
    id_locations: dict[str, set[str]] = defaultdict(set)
    for split, rows in splits.items():
        for row in rows:
            query_targets[row["query_id"]].add(row["target"])
            target_queries[row["target"]].add(row["query_id"])
            query_counts[split][row["query_id"]] += 1
            question_locations[normalize_model_input(row["input"]).casefold()].add(split)
            id_locations[row["id"]].add(split)

    inconsistent_queries = sorted(
        query_id for query_id, targets in query_targets.items() if len(targets) > 1
    )
    if inconsistent_queries:
        raise DatasetError(
            f"query IDs have multiple targets: {inconsistent_queries[:10]}"
        )
    inconsistent_targets = sorted(
        target for target, query_ids in target_queries.items() if len(query_ids) > 1
    )
    if inconsistent_targets:
        raise DatasetError(
            f"targets have multiple query IDs: {inconsistent_targets[:3]}"
        )

    all_queries = set(query_targets)
    missing = {
        split: sorted(all_queries - query_counts[split].keys())
        for split in REQUIRED_SPLITS
        if all_queries - query_counts[split].keys()
    }
    if missing:
        raise DatasetError(f"query IDs missing from splits: {missing}")

    sparse_train = sorted(
        query_id for query_id in all_queries if query_counts["train"][query_id] < 2
    )
    if sparse_train:
        raise DatasetError(f"query IDs have fewer than two train rows: {sparse_train[:10]}")
    for split in ("val", "test"):
        invalid = sorted(
            query_id for query_id in all_queries if query_counts[split][query_id] != 2
        )
        if invalid:
            raise DatasetError(
                f"query IDs must have exactly two {split} rows: {invalid[:10]}"
            )

    for split, report in reports.items():
        counts = [report["register_counts"].get(register, 0) for register in REGISTER_ORDER]
        if max(counts) - min(counts) > 1:
            raise DatasetError(
                f"{split} register counts differ by more than one: {counts}"
            )

    for label, locations in (("inputs", question_locations), ("ids", id_locations)):
        leaked = sorted(key for key, values in locations.items() if len(values) > 1)
        if leaked:
            raise DatasetError(f"{label} cross splits: {leaked[:10]}")

    near_duplicates = _cross_split_near_duplicates(splits)
    if near_duplicates:
        score, left_id, right_id = near_duplicates[0]
        raise DatasetError(
            "near-duplicate questions cross splits: "
            f"{left_id} <> {right_id} ({score:.3f})"
        )

    return {
        "records": sum(report["records"] for report in reports.values()),
        "split_counts": {name: reports[name]["records"] for name in REQUIRED_SPLITS},
        "splits": reports,
    }


def _cross_split_near_duplicates(
    splits: dict[str, list[dict[str, Any]]],
) -> list[tuple[float, str, str]]:
    indexed = {
        split: [
            (row["id"], _character_trigrams(row["input"]))
            for row in splits[split]
        ]
        for split in REQUIRED_SPLITS
    }
    matches: list[tuple[float, str, str]] = []
    for left_index, left_split in enumerate(REQUIRED_SPLITS):
        for right_split in REQUIRED_SPLITS[left_index + 1 :]:
            for left_id, left_grams in indexed[left_split]:
                for right_id, right_grams in indexed[right_split]:
                    score = len(left_grams & right_grams) / len(
                        left_grams | right_grams
                    )
                    if score >= NEAR_DUPLICATE_THRESHOLD:
                        matches.append((score, left_id, right_id))
    return sorted(matches, key=lambda item: (-item[0], item[1], item[2]))


def _character_trigrams(text: str) -> frozenset[str]:
    normalized = normalize_model_input(text).casefold()
    padded = f"  {normalized}  "
    return frozenset(padded[index : index + 3] for index in range(len(padded) - 2))
