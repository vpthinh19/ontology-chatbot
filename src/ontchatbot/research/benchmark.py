"""Test-set contract for direct-SPARQL generation."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from rdflib import Graph

from ..settings import QUERY_CATALOGUE_PATH, TEST_DATASET_PATH, USER_QUERIES_PATH
from ..catalogue import QuerySpec, load_catalogue, match_target
from .dataset import ALLOWED_REGISTERS
from .evaluation import evaluate_predictions
from ..runtime.text import normalize_model_input
from ..runtime.sparql import execute_select, validate_select

REQUIRED_FIELDS = {"id", "query_id", "register", "input", "target"}


class BenchmarkError(ValueError):
    """The benchmark or prediction file violates its contract."""


def load_benchmark(path: Path = TEST_DATASET_PATH) -> list[dict[str, str]]:
    return _load_jsonl(Path(path), kind="benchmark")


def load_user_query_expectations(
    path: Path = USER_QUERIES_PATH,
) -> list[dict[str, str]]:
    """Nạp bộ câu người thật; đây không phải một split sinh tự động.

    Không chốt số lượng ở đây. Bộ này CHỈ ĐƯỢC PHÌNH RA - chín câu ban đầu cộng
    sáu câu thêm ngày 15/8/2026 - nên mọi chỗ ghi cứng "chín câu" đều thành sai
    ngay lần bổ sung kế tiếp.
    """

    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BenchmarkError("real-user cases contain invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("expectations"), list):
        raise BenchmarkError("real-user cases must contain an expectations list")
    expectations = payload["expectations"]
    # ``note`` là trường TUỲ CHỌN, thêm 2026-08-14: nhãn ở tệp này do các phiên
    # làm việc trước SUY RA chứ không phải người gán, nên mỗi lần sửa nhãn phải
    # ghi kèm căn cứ. Bắt buộc hai trường kia, cho phép thêm ``note``.
    required = {"question", "expected_query_id"}
    allowed = required | {"note"}
    for index, item in enumerate(expectations, 1):
        if not isinstance(item, dict) or not required <= set(item) <= allowed:
            raise BenchmarkError(
                f"real-user case {index}: fields must be question and expected_query_id"
                " (optional: note)"
            )
        if not all(isinstance(value, str) and value for value in item.values()):
            raise BenchmarkError(f"real-user case {index}: values must be non-empty text")
    return expectations


def validate_benchmark(
    rows: list[dict[str, Any]],
    graph: Graph,
    *,
    catalogue: Mapping[str, QuerySpec] | None = None,
    training_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    catalogue = catalogue or load_catalogue(QUERY_CATALOGUE_PATH)
    if not rows:
        raise BenchmarkError("benchmark is empty")

    ids: set[str] = set()
    questions: set[str] = set()
    training_questions = {
        normalize_model_input(row["input"]).casefold()
        for row in (training_rows or [])
    }
    training_queries = {row["query_id"] for row in (training_rows or [])}
    training_slots: dict[str, dict[str, set[str]]] = {}
    for row in training_rows or []:
        spec = catalogue.get(row["query_id"])
        if spec is None:
            continue
        matched = match_target(spec, row["target"])
        if matched is None:
            continue
        query_slots = training_slots.setdefault(row["query_id"], {})
        for name, value in matched.items():
            query_slots.setdefault(name, set()).add(value)
    register_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    queries: set[str] = set()
    targets: set[str] = set()
    benchmark_slots: dict[str, dict[str, set[str]]] = {}

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
        normalized = normalize_model_input(row["input"]).casefold()
        if normalized in questions:
            raise BenchmarkError(f"duplicate normalized question: {record_id}")
        if normalized in training_questions:
            raise BenchmarkError(f"question leaks from training data: {record_id}")
        questions.add(normalized)

        register = row["register"]
        if register not in ALLOWED_REGISTERS:
            raise BenchmarkError(f"{record_id}: invalid register {register}")

        target = row["target"]
        if "\n" in target or "\r" in target or re.search(r"\s{2,}", target):
            raise BenchmarkError(f"{record_id}: target must be one canonical line")
        query_id = row["query_id"]
        spec = catalogue.get(query_id)
        if spec is None:
            raise BenchmarkError(f"{record_id}: unknown query_id {query_id}")
        matched = match_target(spec, target)
        if matched is None:
            raise BenchmarkError(
                f"{record_id}: target does not match query family {query_id}"
            )
        query_slots = benchmark_slots.setdefault(query_id, {})
        for name, value in matched.items():
            query_slots.setdefault(name, set()).add(value)
        if spec.domain != "out-of-domain":
            validate_select(target)
            if not execute_select(graph, target):
                raise BenchmarkError(f"{record_id}: reference query returns no rows")
        register_counts[register] += 1
        domain_counts[spec.domain] += 1
        queries.add(query_id)
        targets.add(target)

    missing_queries = sorted(queries - training_queries) if training_rows is not None else []
    if missing_queries:
        raise BenchmarkError(f"query IDs absent from train: {missing_queries[:10]}")
    missing_finite = []
    if training_rows is not None:
        for query_id, slots in benchmark_slots.items():
            spec = catalogue[query_id]
            for name, values in slots.items():
                if not spec.slots[name].values:
                    continue
                unseen = sorted(values - training_slots.get(query_id, {}).get(name, set()))
                if unseen:
                    missing_finite.append((query_id, name, unseen))
    if missing_finite:
        raise BenchmarkError(f"finite slot values absent from train: {missing_finite[:10]}")

    return {
        "records": len(rows),
        "queries": len(queries),
        "targets": len(targets),
        "register_counts": dict(sorted(register_counts.items())),
        "domains": dict(sorted(domain_counts.items())),
        "queries_supported_by_train": len(queries & training_queries),
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
