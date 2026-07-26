"""Execution-based metrics for generated SPARQL."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable

from rdflib import Graph

from .query_engine import SparqlError, execute_select, validate_select


def evaluate_predictions(
    examples: list[dict[str, str]],
    predictions: Iterable[str],
    graph: Graph,
    *,
    include_cases: bool = False,
) -> dict[str, Any]:
    predictions = list(predictions)
    if len(examples) != len(predictions):
        raise ValueError("examples and predictions must have the same length")

    totals: Counter[str] = Counter()
    by_register: dict[str, Counter[str]] = defaultdict(Counter)
    cases = []
    for example, prediction in zip(examples, predictions, strict=True):
        target = example["target"]
        register = example["register"]
        totals["count"] += 1
        by_register[register]["count"] += 1

        parse_ok = False
        execution_ok = False
        answer_exact = False
        error = None
        predicted_rows = None
        try:
            validate_select(prediction)
            parse_ok = True
            predicted_rows = execute_select(graph, prediction)
            execution_ok = True
            reference_rows = execute_select(graph, target)
            answer_exact = _row_key(predicted_rows) == _row_key(reference_rows)
        except SparqlError as exc:
            error = str(exc)

        canonical_exact = prediction.strip() == target
        for name, value in (
            ("parse", parse_ok),
            ("execution", execution_ok),
            ("answer_exact", answer_exact),
            ("canonical_exact", canonical_exact),
        ):
            totals[name] += int(value)
            by_register[register][name] += int(value)

        if include_cases:
            cases.append(
                {
                    "id": example["id"],
                    "register": register,
                    "input": example["input"],
                    "target": target,
                    "prediction": prediction,
                    "parse": parse_ok,
                    "execution": execution_ok,
                    "answer_exact": answer_exact,
                    "canonical_exact": canonical_exact,
                    "error": error,
                    "predicted_rows": predicted_rows,
                }
            )

    report = {
        "overall": _rates(totals),
        "by_register": {
            register: _rates(counts)
            for register, counts in sorted(by_register.items())
        },
    }
    if include_cases:
        report["cases"] = cases
    return report


def _row_key(rows: list[dict[str, object]]) -> tuple:
    return tuple(
        sorted(
            (
                tuple(sorted((column, _value_key(value)) for column, value in row.items()))
                for row in rows
            ),
            key=repr,
        )
    )


def _value_key(value: object) -> tuple[str, str]:
    if value is None:
        return ("none", "")
    return (type(value).__name__, str(value))


def _rates(counts: Counter[str]) -> dict[str, int | float]:
    total = counts["count"]
    return {
        "count": total,
        "parse_rate": counts["parse"] / total if total else 0.0,
        "execution_rate": counts["execution"] / total if total else 0.0,
        "answer_exact_rate": counts["answer_exact"] / total if total else 0.0,
        "canonical_query_exact_rate": counts["canonical_exact"] / total if total else 0.0,
    }
