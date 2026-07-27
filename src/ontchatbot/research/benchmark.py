"""Test-set contract for direct-SPARQL generation."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rdflib import Graph

from ..settings import TEST_DATASET_PATH
from .dataset import (
    ALLOWED_QUERY_SHAPES,
    ALLOWED_REGISTERS,
    UNSUPPORTED_TARGET_CHARACTERS,
)
from .evaluation import evaluate_predictions
from ..runtime.text import normalize_model_input
from ..runtime.sparql import execute_select, validate_select

REQUIRED_FIELDS = {"id", "family_id", "register", "query_shape", "input", "target"}
_LOCAL_TERM = re.compile(r"(?<![A-Za-z0-9]):([A-Za-z][A-Za-z0-9]*)")


class BenchmarkError(ValueError):
    """The benchmark or prediction file violates its contract."""


def load_benchmark(path: Path = TEST_DATASET_PATH) -> list[dict[str, str]]:
    return _load_jsonl(Path(path), kind="benchmark")


def validate_benchmark(
    rows: list[dict[str, Any]],
    graph: Graph,
    *,
    training_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not rows:
        raise BenchmarkError("benchmark is empty")

    ids: set[str] = set()
    questions: set[str] = set()
    training_questions = {
        normalize_model_input(row["input"]).casefold()
        for row in (training_rows or [])
    }
    training_families = {row["family_id"] for row in (training_rows or [])}
    training_targets = {row["target"] for row in (training_rows or [])}
    training_terms = {
        term
        for row in (training_rows or [])
        for term in _LOCAL_TERM.findall(row["target"])
    }
    register_counts: Counter[str] = Counter()
    shape_counts: Counter[str] = Counter()
    targets: set[str] = set()

    for index, row in enumerate(rows, 1):
        record_id = str(row.get("id", f"line-{index}"))
        if set(row) != REQUIRED_FIELDS:
            raise BenchmarkError(
                f"{record_id}: fields must be exactly {sorted(REQUIRED_FIELDS)}"
            )
        if not all(isinstance(row[field], str) and row[field] for field in REQUIRED_FIELDS):
            raise BenchmarkError(f"{record_id}: every field must be a non-empty string")
        if record_id in ids:
            raise BenchmarkError(f"duplicate id: {record_id}")
        ids.add(record_id)
        if row["family_id"] in training_families:
            raise BenchmarkError(f"semantic family leaks from training data: {record_id}")

        normalized = normalize_model_input(row["input"]).casefold()
        if normalized in questions:
            raise BenchmarkError(f"duplicate normalized question: {record_id}")
        if normalized in training_questions:
            raise BenchmarkError(f"question leaks from training data: {record_id}")
        questions.add(normalized)

        register = row["register"]
        shape = row["query_shape"]
        if register not in ALLOWED_REGISTERS:
            raise BenchmarkError(f"{record_id}: invalid register {register}")
        if shape not in ALLOWED_QUERY_SHAPES:
            raise BenchmarkError(f"{record_id}: invalid query shape {shape}")

        target = row["target"]
        if "\n" in target or "\r" in target or re.search(r"\s{2,}", target):
            raise BenchmarkError(f"{record_id}: target must be one canonical line")
        unsupported = sorted(set(target) & UNSUPPORTED_TARGET_CHARACTERS)
        if unsupported:
            raise BenchmarkError(
                f"{record_id}: tokenizer-unsafe target characters: {unsupported}"
            )
        validate_select(target)
        if not execute_select(graph, target):
            raise BenchmarkError(f"{record_id}: reference query returns no rows")
        register_counts[register] += 1
        shape_counts[shape] += 1
        targets.add(target)

    repeated_targets = sorted(targets & training_targets)
    if repeated_targets:
        raise BenchmarkError(
            f"test targets must be held out from model-selection data: {repeated_targets[:3]}"
        )
    test_terms = {term for target in targets for term in _LOCAL_TERM.findall(target)}
    missing_terms = sorted(test_terms - training_terms) if training_rows is not None else []
    if missing_terms:
        raise BenchmarkError(f"test uses schema terms absent from training: {missing_terms}")

    return {
        "records": len(rows),
        "targets": len(targets),
        "register_counts": dict(sorted(register_counts.items())),
        "query_shape_counts": dict(sorted(shape_counts.items())),
        "targets_seen_in_model_selection_data": len(repeated_targets),
        "schema_terms_missing_from_training": missing_terms,
    }


def load_predictions(path: Path) -> dict[str, str]:
    rows = _load_jsonl(Path(path), kind="predictions")
    predictions: dict[str, str] = {}
    for line_number, row in enumerate(rows, 1):
        if set(row) != {"id", "prediction"}:
            raise BenchmarkError(
                f"prediction line {line_number}: fields must be id and prediction"
            )
        if not isinstance(row["id"], str) or not isinstance(row["prediction"], str):
            raise BenchmarkError(f"prediction line {line_number}: values must be strings")
        if row["id"] in predictions:
            raise BenchmarkError(f"duplicate prediction id: {row['id']}")
        predictions[row["id"]] = row["prediction"]
    return predictions


def reference_predictions(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["id"]: row["target"] for row in rows}


def evaluate_benchmark(
    rows: list[dict[str, str]],
    predictions: Mapping[str, str],
    graph: Graph,
    *,
    include_cases: bool = False,
) -> dict[str, Any]:
    expected_ids = {row["id"] for row in rows}
    missing = sorted(expected_ids - predictions.keys())
    unexpected = sorted(predictions.keys() - expected_ids)
    ordered = [predictions.get(row["id"], "") for row in rows]
    report = evaluate_predictions(rows, ordered, graph, include_cases=include_cases)
    report["prediction_file"] = {
        "missing_ids": missing,
        "unexpected_ids": unexpected,
    }
    return report


def _load_jsonl(path: Path, *, kind: str) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise BenchmarkError(f"{kind} line {line_number}: invalid JSON") from exc
        if not isinstance(row, dict):
            raise BenchmarkError(f"{kind} line {line_number}: record must be an object")
        rows.append(row)
    return rows
