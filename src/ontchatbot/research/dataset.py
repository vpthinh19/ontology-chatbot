"""Loading and executable validation for the canonical dataset."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from rdflib import Graph

from ..runtime.sparql import execute_select, validate_select
from ..runtime.text import normalize_model_input
from ..settings import DATASET_DIR

REQUIRED_FIELDS = {"id", "family_id", "register", "input", "target"}
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


def build_in_domain_release(
    rows: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Build the deterministic in-domain train, validation, and test splits."""

    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_target[row["target"]].append(row)
    targets = sorted(
        by_target,
        key=lambda target: min(row["id"] for row in by_target[target]),
    )
    release = {split: [] for split in REQUIRED_SPLITS}
    register_counts = {split: Counter() for split in REQUIRED_SPLITS}

    for target_index, target in enumerate(targets):
        query_id = f"query-{target_index + 1:04d}"
        pools = {
            register: sorted(
                (
                    {
                        "id": row["id"],
                        "query_id": query_id,
                        "register": row["register"],
                        "input": row["input"],
                        "target": row["target"],
                    }
                    for row in by_target[target]
                    if row["register"] == register
                ),
                key=lambda row: row["id"],
            )
            for register in REGISTER_ORDER
        }
        for split, offset in (("val", 0), ("test", 1)):
            available = [register for register in REGISTER_ORDER if pools[register]]
            register = min(
                available,
                key=lambda value: (
                    register_counts[split][value],
                    (REGISTER_ORDER.index(value) - target_index - offset) % 4,
                ),
            )
            release[split].append(pools[register].pop(0))
            register_counts[split][register] += 1
        for register in REGISTER_ORDER:
            release["train"].extend(pools[register])
            register_counts["train"][register] += len(pools[register])

    _repair_in_domain_release(release, register_counts)
    for split in REQUIRED_SPLITS:
        release[split].sort(key=lambda row: row["id"])
    return release


def _repair_in_domain_release(
    release: dict[str, list[dict[str, str]]],
    register_counts: dict[str, Counter[str]],
) -> None:
    """Remove cross-split near duplicates without weakening register balance."""

    rows_by_id = {
        row["id"]: row
        for split in REQUIRED_SPLITS
        for row in release[split]
    }
    split_by_id = {
        row["id"]: split
        for split in REQUIRED_SPLITS
        for row in release[split]
    }
    ids_by_target: dict[str, list[str]] = defaultdict(list)
    for row in rows_by_id.values():
        ids_by_target[row["target"]].append(row["id"])

    near_pairs = _near_duplicate_id_pairs(rows_by_id.values())
    candidates = [
        (target, left_id, right_id)
        for target in sorted(ids_by_target)
        for left_id, right_id in combinations(sorted(ids_by_target[target]), 2)
    ]

    def objective() -> tuple[int, int, int]:
        cross_split_count = sum(
            split_by_id[left_id] != split_by_id[right_id]
            for left_id, right_id in near_pairs
        )
        ranges = [
            max(register_counts[split][register] for register in REGISTER_ORDER)
            - min(register_counts[split][register] for register in REGISTER_ORDER)
            for split in REQUIRED_SPLITS
        ]
        return cross_split_count, max(ranges), sum(ranges)

    def swap(left_id: str, right_id: str) -> None:
        left_split = split_by_id[left_id]
        right_split = split_by_id[right_id]
        left_register = rows_by_id[left_id]["register"]
        right_register = rows_by_id[right_id]["register"]
        split_by_id[left_id], split_by_id[right_id] = right_split, left_split
        register_counts[left_split][left_register] -= 1
        register_counts[left_split][right_register] += 1
        register_counts[right_split][right_register] -= 1
        register_counts[right_split][left_register] += 1

    while True:
        current = objective()
        best = current
        best_pair: tuple[str, str] | None = None
        for _, left_id, right_id in candidates:
            if split_by_id[left_id] == split_by_id[right_id]:
                continue
            swap(left_id, right_id)
            candidate = objective()
            swap(left_id, right_id)
            if candidate < best:
                best = candidate
                best_pair = left_id, right_id
        if best_pair is None:
            break
        swap(*best_pair)

    cross_split_count, maximum_range, _ = objective()
    if cross_split_count or maximum_range > 1:
        raise DatasetError(
            "cannot build balanced splits without cross-split near duplicates"
        )

    allocated_rows = list(rows_by_id.values())
    for split in REQUIRED_SPLITS:
        release[split] = [
            row for row in allocated_rows if split_by_id[row["id"]] == split
        ]


def _near_duplicate_id_pairs(
    rows: Any,
) -> list[tuple[str, str]]:
    indexed = sorted(
        ((row["id"], _character_trigrams(row["input"])) for row in rows),
        key=lambda item: item[0],
    )
    pairs: list[tuple[str, str]] = []
    for index, (left_id, left_grams) in enumerate(indexed):
        for right_id, right_grams in indexed[index + 1 :]:
            score = len(left_grams & right_grams) / len(left_grams | right_grams)
            if score >= NEAR_DUPLICATE_THRESHOLD:
                pairs.append((left_id, right_id))
    return pairs


def validate_dataset(rows: list[dict[str, Any]], graph: Graph) -> dict[str, Any]:
    """Validate one split without relying on a field that duplicates its filename."""

    if not rows:
        raise DatasetError("dataset split is empty")

    ids: set[str] = set()
    normalized_inputs: dict[str, str] = {}
    family_targets: dict[str, set[str]] = defaultdict(set)
    family_registers: dict[str, Counter[str]] = defaultdict(Counter)
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

        family_targets[row["family_id"]].add(target)
        family_registers[row["family_id"]][register] += 1
        register_counts[register] += 1
        target_counts[target] += 1

    inconsistent = sorted(family for family, targets in family_targets.items() if len(targets) > 1)
    if inconsistent:
        raise DatasetError(f"families have multiple targets: {inconsistent[:10]}")

    expected_registers = Counter({register: 1 for register in ALLOWED_REGISTERS})
    invalid_registers = sorted(
        family
        for family, counts in family_registers.items()
        if counts != expected_registers
    )
    if invalid_registers:
        raise DatasetError(
            "families must contain exactly one of each register: "
            f"{invalid_registers[:10]}"
        )

    return {
        "records": len(rows),
        "families": len(family_targets),
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
