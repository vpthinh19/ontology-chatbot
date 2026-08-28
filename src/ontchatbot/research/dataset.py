"""Loading and executable validation for the canonical dataset."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from rdflib import Graph

from .graph import execute_select, validate_select
from ..runtime.cards import CardLookup
from ..runtime.text import normalize_model_input
from ..settings import DATASET_DIR, QUERY_CATALOGUE_PATH
from ..catalogue import QuerySpec, load_catalogue, match_target

REQUIRED_FIELDS = {"id", "query_id", "register", "input", "target"}
REQUIRED_SPLITS = ("train", "val", "test")
ALLOWED_REGISTERS = {"formal", "neutral", "colloquial", "noisy"}
REGISTER_ORDER = ("formal", "neutral", "colloquial", "noisy")
TRAIN_MIN_ROWS_PER_QUERY = 4
HELD_OUT_MIN_ROWS_PER_QUERY = 2
HELD_OUT_MIN_REGISTERS_PER_QUERY = 2
# Reporting is migrated to the minimum-cardinality names in Task 8.
HELD_OUT_ROWS_PER_QUERY = HELD_OUT_MIN_ROWS_PER_QUERY
HELD_OUT_REGISTERS_PER_QUERY = HELD_OUT_MIN_REGISTERS_PER_QUERY
NEAR_DUPLICATE_THRESHOLD = 0.84


class DatasetError(ValueError):
    """The dataset violates its declared contract."""


def load_dataset(path: Path) -> list[dict[str, Any]]:
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


def load_release(directory: Path = DATASET_DIR) -> dict[str, list[dict[str, Any]]]:
    """Load the three standard dataset files."""

    directory = Path(directory)
    return {split: load_dataset(directory / f"{split}.jsonl") for split in REQUIRED_SPLITS}


def validate_dataset(
    rows: list[dict[str, Any]],
    graph: Graph,
    catalogue: Mapping[str, QuerySpec] | None = None,
    *,
    _lookup: CardLookup | None = None,
) -> dict[str, Any]:
    """Validate one split against catalogue templates and the ontology."""

    catalogue = catalogue or load_catalogue(QUERY_CATALOGUE_PATH)
    lookup = _lookup or CardLookup()
    if not rows:
        raise DatasetError("dataset split is empty")

    ids: set[str] = set()
    normalized_inputs: dict[str, str] = {}
    register_counts: Counter[str] = Counter()
    target_counts: Counter[tuple[str, tuple[str, ...]]] = Counter()
    query_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    slot_values: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    # Thousands of rows share a few hundred targets, and a target either returns
    # rows or it does not - running it again per row cannot learn anything new.
    answering_targets: set[tuple[str, tuple[str, ...]]] = set()

    for index, row in enumerate(rows, 1):
        record_id = str(row.get("id", f"line-{index}"))
        _validate_row_shape(row, record_id)
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

        query_id = row["query_id"]
        spec = catalogue.get(query_id)
        if spec is None:
            raise DatasetError(f"{record_id}: unknown query_id {query_id}")
        target = row["target"]
        _validate_target_text(target, record_id)
        label = (query_id, tuple(target))
        try:
            query = lookup.query(query_id, target)
        except KeyError:
            raise DatasetError(
                f"{record_id}: target does not match query family {query_id}"
            ) from None
        matched = match_target(spec, query)
        if matched is None:
            raise DatasetError(f"{record_id}: target does not match query family {query_id}")
        for name, value in matched.items():
            slot_values[query_id][name].add(value)

        if spec.domain != "out-of-domain":
            validate_select(query)
            if label not in answering_targets:
                if not execute_select(graph, query):
                    raise DatasetError(f"{record_id}: reference query returns no rows")
                answering_targets.add(label)

        register_counts[register] += 1
        target_counts[label] += 1
        query_counts[query_id] += 1
        domain_counts[spec.domain] += 1

    return {
        "records": len(rows),
        "queries": len(query_counts),
        "targets": len(target_counts),
        "query_counts": dict(sorted(query_counts.items())),
        "register_counts": dict(sorted(register_counts.items())),
        "domains": dict(sorted(domain_counts.items())),
        "slot_values": {
            query_id: {name: sorted(values) for name, values in sorted(slots.items())}
            for query_id, slots in sorted(slot_values.items())
        },
    }


def validate_release(
    splits: dict[str, list[dict[str, Any]]],
    graph: Graph,
    catalogue: Mapping[str, QuerySpec] | None = None,
    *,
    require_complete_catalogue: bool = True,
    lookup: CardLookup | None = None,
) -> dict[str, Any]:
    """Validate all files, train coverage, and leakage between splits."""

    catalogue = catalogue or load_catalogue(QUERY_CATALOGUE_PATH)
    lookup = lookup or CardLookup()
    if set(splits) != set(REQUIRED_SPLITS):
        raise DatasetError(f"release must contain exactly {list(REQUIRED_SPLITS)}")
    reports = {
        name: validate_dataset(rows, graph, catalogue, _lookup=lookup)
        for name, rows in splits.items()
    }

    query_counts = {split: Counter() for split in REQUIRED_SPLITS}
    query_registers = {split: defaultdict(set) for split in REQUIRED_SPLITS}
    question_locations: dict[str, set[str]] = defaultdict(set)
    id_locations: dict[str, set[str]] = defaultdict(set)
    row_locations: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    train_slots: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    domains: Counter[str] = Counter()
    for split, rows in splits.items():
        for row in rows:
            query_id = row["query_id"]
            query_counts[split][query_id] += 1
            query_registers[split][query_id].add(row["register"])
            normalized = normalize_model_input(row["input"]).casefold()
            question_locations[normalized].add(split)
            id_locations[row["id"]].add(split)
            row_locations[query_id].append((split, row))
            spec = catalogue[query_id]
            domains[spec.domain] += 1
            if split == "train":
                query = lookup.query(query_id, row["target"])
                for name, value in (match_target(spec, query) or {}).items():
                    train_slots[query_id][name].add(value)

    # Chỉ họ primary phải có dữ liệu huấn luyện. Họ secondary chỉ hỗ trợ runtime.
    # Các họ secondary xuất hiện trong dataset không phải thỏa mọi điều kiện phủ.
    primary_queries = {
        query_id for query_id, spec in catalogue.items() if spec.tier == "primary"
    }
    observed_queries = set().union(*(counts.keys() for counts in query_counts.values()))
    checked_queries = (
        primary_queries
        if require_complete_catalogue
        else observed_queries & primary_queries
    )
    missing = {
        split: sorted(checked_queries - query_counts[split].keys())
        for split in REQUIRED_SPLITS
        if checked_queries - query_counts[split].keys()
    }
    if missing:
        raise DatasetError(f"query IDs missing from splits: {missing}")

    sparse_train = sorted(
        query_id
        for query_id in checked_queries
        if query_counts["train"][query_id] < TRAIN_MIN_ROWS_PER_QUERY
    )
    if sparse_train:
        raise DatasetError(f"query IDs have fewer than four train rows: {sparse_train[:10]}")
    missing_train_registers = {
        query_id: sorted(ALLOWED_REGISTERS - query_registers["train"][query_id])
        for query_id in sorted(checked_queries)
        if ALLOWED_REGISTERS - query_registers["train"][query_id]
    }
    if missing_train_registers:
        raise DatasetError(
            "query IDs have missing train registers: "
            f"{list(missing_train_registers.items())[:10]}"
        )
    for split in ("val", "test"):
        sparse = sorted(
            query_id
            for query_id in checked_queries
            if query_counts[split][query_id] < HELD_OUT_MIN_ROWS_PER_QUERY
        )
        if sparse:
            raise DatasetError(f"query IDs have fewer than two {split} rows: {sparse[:10]}")
        repeated = sorted(
            query_id
            for query_id in checked_queries
            if len(query_registers[split][query_id]) < HELD_OUT_MIN_REGISTERS_PER_QUERY
        )
        if repeated:
            raise DatasetError(
                f"query IDs must use two distinct {split} registers: {repeated[:10]}"
            )

    slot_coverage = _slot_coverage(
        {query_id: catalogue[query_id] for query_id in sorted(checked_queries)},
        train_slots,
    )
    missing_slots = [
        (query_id, name, details["missing_train"])
        for query_id, slots in slot_coverage.items()
        for name, details in slots.items()
        if details["missing_train"]
    ]
    if require_complete_catalogue and missing_slots:
        raise DatasetError(f"finite slot values missing from train: {missing_slots[:10]}")

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
        "domains": dict(sorted(domains.items())),
        "catalogue_coverage_required": require_complete_catalogue,
        # Hai con số này KHÁC nhau và không được gộp: "catalogue phủ đầy đủ" rất
        # dễ bị đọc thành "model trả lời được đầy đủ". Một họ secondary chạy được
        # ở runtime không có nghĩa model từng được dạy để sinh ra nó.
        "families": {
            "runtime_supported": len(catalogue),
            "training_covered": len(primary_queries),
        },
        "slot_coverage": slot_coverage,
        "splits": reports,
    }


def _validate_row_shape(row: dict[str, Any], record_id: str) -> None:
    if set(row) != REQUIRED_FIELDS:
        raise DatasetError(
            f"{record_id}: fields must be exactly {sorted(REQUIRED_FIELDS)}, got {sorted(row)}"
        )
    text_fields = REQUIRED_FIELDS - {"target"}
    if not all(isinstance(row[field], str) and row[field] for field in text_fields):
        raise DatasetError(f"{record_id}: every text field must be a non-empty string")
    _validate_target_text(row["target"], record_id)


def _validate_target_text(target: object, record_id: str) -> None:
    if not isinstance(target, list) or not all(
        isinstance(value, str) and value for value in target
    ):
        raise DatasetError(f"{record_id}: target must be a list of non-empty IRIs")


def _slot_coverage(
    catalogue: Mapping[str, QuerySpec],
    train_slots: Mapping[str, Mapping[str, set[str]]],
) -> dict[str, dict[str, dict[str, list[str]]]]:
    coverage: dict[str, dict[str, dict[str, list[str]]]] = {}
    for query_id, spec in catalogue.items():
        slot_report = {}
        for name, slot in spec.slots.items():
            seen = sorted(train_slots.get(query_id, {}).get(name, set()))
            declared = list(slot.values)
            slot_report[name] = {
                "declared": declared,
                "seen_train": seen,
                "missing_train": sorted(set(declared) - set(seen)),
            }
        coverage[query_id] = slot_report
    return coverage


def _cross_split_near_duplicates(
    splits: dict[str, list[dict[str, Any]]],
) -> list[tuple[float, str, str]]:
    indexed = {
        split: [
            (row["id"], row["query_id"], _character_trigrams(row["input"]))
            for row in splits[split]
        ]
        for split in REQUIRED_SPLITS
    }
    matches: list[tuple[float, str, str]] = []
    for left_index, left_split in enumerate(REQUIRED_SPLITS):
        for right_split in REQUIRED_SPLITS[left_index + 1 :]:
            for left_id, left_query, left_grams in indexed[left_split]:
                for right_id, right_query, right_grams in indexed[right_split]:
                    if left_query != right_query:
                        continue
                    score = len(left_grams & right_grams) / len(left_grams | right_grams)
                    if score >= NEAR_DUPLICATE_THRESHOLD:
                        matches.append((score, left_id, right_id))
    return sorted(matches, key=lambda item: (-item[0], item[1], item[2]))


def _character_trigrams(text: str) -> frozenset[str]:
    normalized = normalize_model_input(text).casefold()
    padded = f"  {normalized}  "
    return frozenset(padded[index : index + 3] for index in range(len(padded) - 2))
