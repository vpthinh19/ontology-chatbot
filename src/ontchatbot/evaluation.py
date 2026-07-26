"""Execution-based metrics for generated SPARQL."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Iterable

from rdflib import Graph

from .query_engine import SparqlError, execute_select, validate_select

_PREFIXED_NAME = re.compile(r":[A-Za-z][A-Za-z0-9]*")
_STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')


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
    grouped: dict[str, dict[str, Counter[str]]] = {
        "register": defaultdict(Counter),
        "query_shape": defaultdict(Counter),
    }
    error_counts: Counter[str] = Counter()
    cases = []
    for example, prediction in zip(examples, predictions, strict=True):
        target = example["target"]
        register = example["register"]
        totals["count"] += 1
        groups = {"register": register}
        if example.get("query_shape"):
            groups["query_shape"] = example["query_shape"]
        for group_name, value in groups.items():
            grouped[group_name][value]["count"] += 1

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
        error_category = _error_category(
            target,
            prediction,
            parse_ok=parse_ok,
            execution_ok=execution_ok,
            answer_exact=answer_exact,
            graph=graph,
        )
        if error_category is not None:
            error_counts[error_category] += 1
        for name, value in (
            ("parse", parse_ok),
            ("execution", execution_ok),
            ("answer_exact", answer_exact),
            ("canonical_exact", canonical_exact),
        ):
            totals[name] += int(value)
            for group_name, group_value in groups.items():
                grouped[group_name][group_value][name] += int(value)

        if include_cases:
            cases.append(
                {
                    "id": example["id"],
                    "register": register,
                    "query_shape": example.get("query_shape"),
                    "input": example["input"],
                    "target": target,
                    "prediction": prediction,
                    "parse": parse_ok,
                    "execution": execution_ok,
                    "answer_exact": answer_exact,
                    "canonical_exact": canonical_exact,
                    "error": error,
                    "error_category": error_category,
                    "predicted_rows": predicted_rows,
                }
            )

    report = {
        "overall": _rates(totals),
        "by_register": _group_rates(grouped["register"]),
        "error_counts": dict(sorted(error_counts.items())),
    }
    if grouped["query_shape"]:
        report["by_query_shape"] = _group_rates(grouped["query_shape"])
    if include_cases:
        report["cases"] = cases
    return report


def _error_category(
    target: str,
    prediction: str,
    *,
    parse_ok: bool,
    execution_ok: bool,
    answer_exact: bool,
    graph: Graph,
) -> str | None:
    """Give a compact diagnostic for a failed answer.

    This classification is intentionally secondary to execution-based metrics.
    It compares the canonical target vocabulary and branch count, rather than
    pretending to prove full SPARQL equivalence.
    """

    if not parse_ok:
        return "parse_error"
    if not execution_ok:
        return "execution_error"
    if answer_exact:
        return None

    target_triples = target.count(" .")
    prediction_triples = prediction.count(" .")
    if prediction_triples < target_triples:
        return "missing_branch"
    if prediction_triples > target_triples:
        return "extra_branch"
    if set(_STRING_LITERAL.findall(prediction)) != set(_STRING_LITERAL.findall(target)):
        return "wrong_literal"

    from rdflib import OWL, RDF, URIRef

    property_types = {OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property}
    properties = {
        str(subject).rsplit("#", 1)[-1]
        for subject, object_type in graph.subject_objects(RDF.type)
        if object_type in property_types and isinstance(subject, URIRef)
    }
    target_names = {name[1:] for name in _PREFIXED_NAME.findall(target)}
    prediction_names = {name[1:] for name in _PREFIXED_NAME.findall(prediction)}
    if (target_names & properties) != (prediction_names & properties):
        return "wrong_property"
    if (target_names - properties) != (prediction_names - properties):
        return "wrong_iri"
    return "semantic_mismatch"


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


def _group_rates(groups: dict[str, Counter[str]]) -> dict[str, dict[str, int | float]]:
    return {name: _rates(counts) for name, counts in sorted(groups.items())}
