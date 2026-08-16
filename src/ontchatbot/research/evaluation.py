"""Structural primary metrics and execution diagnostics for generated SPARQL."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any, Iterable

from pyparsing import ParseResults
from rdflib import OWL, RDF, Graph, URIRef
from rdflib.plugins.sparql.parser import parseQuery
from rdflib.plugins.sparql.parserutils import CompValue

from ..catalogue import QuerySpec, load_catalogue, match_target
from ..runtime.sparql import PREFIXES, SparqlError, execute_select, validate_select
from ..settings import ONTOLOGY_NS, QUERY_CATALOGUE_PATH
from .query_features import extract_query_features, query_feature_tags

_PREFIXED_NAME = re.compile(r":[A-Za-z][A-Za-z0-9]*")
_STRING_LITERAL = re.compile(r'"(?:[^"\\]|\\.)*"')
_NO_INFORMATION = "không có thông tin"



def _anchor_kind(node: str) -> str:
    """Node được HỎI bằng nội dung hay bằng toạ độ văn bản.

    Ba nhóm, và chênh lệch giữa chúng là thứ giải thích phần lớn lỗi:
    ``table`` được hỏi bằng nội dung ("xếp loại tốt nghiệp"), ``document-part``
    được hỏi bằng chính toạ độ ("Điều 12 Quy chế 1052"), ``named`` là node có
    tên mang nghĩa. Đo trên test 16/8: 26,7% - 97,1% - 90,4%.
    """

    if node.endswith("Table") or re.search(r"Table\d+$", node):
        return "table"
    if re.search(r"Article\d|Clause\d|Appendix|Chapter\d|Point\d", node):
        return "document-part"
    return "named"


def evaluate_predictions(
    examples: list[dict[str, str]],
    predictions: Iterable[str],
    graph: Graph,
    *,
    include_cases: bool = False,
    catalogue: Mapping[str, QuerySpec] | None = None,
) -> dict[str, Any]:
    predictions = list(predictions)
    if len(examples) != len(predictions):
        raise ValueError("examples and predictions must have the same length")

    catalogue = catalogue or load_catalogue(QUERY_CATALOGUE_PATH)
    totals: Counter[str] = Counter()
    in_domain: Counter[str] = Counter()
    out_of_domain: Counter[str] = Counter()
    grouped: dict[str, dict[str, Counter[str]]] = {
        "register": defaultdict(Counter),
        "query_feature": defaultdict(Counter),
        "query_id": defaultdict(Counter),
        "domain": defaultdict(Counter),
        "anchor_kind": defaultdict(Counter),
    }
    object_properties = frozenset(
        str(subject).rsplit("#", 1)[-1]
        for subject in graph.subjects(RDF.type, OWL.ObjectProperty)
        if isinstance(subject, URIRef)
    )
    error_counts: Counter[str] = Counter()
    primary: dict[str, Counter[str]] = {
        "node_selection": Counter(),
        "query_shape": Counter(),
        "rejection_decision": Counter(),
    }
    accounting: Counter[str] = Counter()
    cases = []
    for example, prediction in zip(examples, predictions, strict=True):
        target = example["target"]
        register = example["register"]
        query_id = example["query_id"]
        marker_reference = target == _NO_INFORMATION
        # Chỉ còn HAI nhóm. Họ "liệt kê năng lực" đã bị bỏ khỏi thiết kế
        # (2026-08-14): công cụ chỉ truy ra dữ kiện hoặc nói không có, còn việc
        # giới thiệu phạm vi là của LLM lớn gọi nó.
        evaluation_group = "out_of_domain" if marker_reference else "node_queries"
        accounting[evaluation_group] += 1
        query_features = (
            {}
            if marker_reference
            else extract_query_features(target, object_properties=object_properties)
        )
        totals["count"] += 1
        scope_counts = out_of_domain if marker_reference else in_domain
        scope_counts["count"] += 1
        if marker_reference:
            totals["marker_count"] += 1
            scope_counts["marker_count"] += 1
        else:
            totals["sparql_count"] += 1
            scope_counts["sparql_count"] += 1
        groups = {
            "register": (register,),
            "query_feature": (
                () if marker_reference else query_feature_tags(query_features)
            ),
            "query_id": (query_id,),
            "domain": (
                (catalogue[query_id].domain,) if query_id in catalogue else ()
            ),
        }
        for group_name, values in groups.items():
            for value in values:
                grouped[group_name][value]["count"] += 1
                grouped[group_name][value][
                    "marker_count" if marker_reference else "sparql_count"
                ] += 1

        parse_ok = False
        execution_ok = False
        answer_exact = False
        result_precision = 0.0
        result_recall = 0.0
        result_f1 = 0.0
        error = None
        predicted_rows = None
        canonical_exact = prediction.strip() == target
        marker_exact = marker_reference and canonical_exact
        false_acceptance = False
        safe_rejection = False
        predicted_query_id = None
        predicted_slots: dict[str, str] = {}
        expected_slots: dict[str, str] = {}
        expected_nodes: tuple[str, ...] = ()
        predicted_nodes: tuple[str, ...] = ()
        node_correct: bool | None = None
        shape_correct: bool | None = None
        if marker_reference:
            answer_exact = marker_exact
            if not marker_exact:
                try:
                    validate_select(prediction)
                    parse_ok = True
                    predicted_rows = execute_select(graph, prediction)
                    execution_ok = True
                    false_acceptance = bool(predicted_rows)
                except SparqlError as exc:
                    error = str(exc)
            error_category = (
                None
                if marker_exact
                else "false_acceptance" if false_acceptance else "rejection_mismatch"
            )
            safe_rejection = not false_acceptance
        else:
            try:
                validate_select(prediction)
                parse_ok = True
                predicted_rows = execute_select(graph, prediction)
                execution_ok = True
                reference_rows = execute_select(graph, target)
                answer_exact = _row_key(predicted_rows) == _row_key(reference_rows)
                result_precision, result_recall, result_f1 = _result_scores(
                    predicted_rows,
                    reference_rows,
                )
            except SparqlError as exc:
                error = str(exc)
            error_category = _error_category(
                target,
                prediction,
                parse_ok=parse_ok,
                execution_ok=execution_ok,
                answer_exact=answer_exact,
                graph=graph,
            )

        # Ba thước chính không dựa vào tập kết quả. Một query chỉ được xem là
        # đầu ra được hệ thống chấp nhận khi nó vừa hợp cú pháp vừa khớp một họ
        # catalogue; điều này đúng với cả causal LM và seq2seq vì cả hai cùng
        # sinh ra đúng một chuỗi đích.
        if parse_ok:
            predicted_query_id, predicted_slots = _match_catalogue(
                catalogue,
                prediction.strip(),
            )
        rejection_correct = (
            marker_exact if marker_reference else predicted_query_id is not None
        )
        primary["rejection_decision"]["count"] += 1
        primary["rejection_decision"]["correct"] += int(rejection_correct)

        if not marker_reference:
            expected_spec = catalogue.get(query_id)
            if expected_spec is not None:
                expected_slots = match_target(expected_spec, target) or {}
            non_node_slots = (
                {
                    name
                    for name, slot in expected_spec.slots.items()
                    if slot.kind != "iri"
                }
                if expected_spec is not None
                else set()
            )
            shape_correct = predicted_query_id == query_id and all(
                predicted_slots.get(name) == expected_slots.get(name)
                for name in non_node_slots
            )
            primary["query_shape"]["count"] += 1
            primary["query_shape"]["correct"] += int(shape_correct)

        if evaluation_group == "node_queries":
            expected_nodes = _query_anchor_nodes(target, graph)
            # NHÓM THEO KIỂU TÊN NODE. Phép chia này đã phải viết lại bằng script
            # vứt đi ba lần để chẩn đoán, vì báo cáo không có nó: bảng bị hỏi
            # bằng NỘI DUNG nhưng từng được đặt tên bằng TOẠ ĐỘ, còn điều/khoản
            # thì được hỏi bằng chính toạ độ của nó. Hai chuyện khác hẳn nhau mà
            # gộp chung thì không thấy gì.
            if expected_nodes:
                kind = _anchor_kind(expected_nodes[0])
                groups["anchor_kind"] = (kind,)
                grouped["anchor_kind"][kind]["count"] += 1
                grouped["anchor_kind"][kind]["sparql_count"] += 1
            if parse_ok:
                predicted_nodes = _query_anchor_nodes(prediction, graph)
            node_correct = bool(expected_nodes) and predicted_nodes == expected_nodes
            primary["node_selection"]["count"] += 1
            primary["node_selection"]["correct"] += int(node_correct)
        system_answer_exact = safe_rejection if marker_reference else answer_exact
        if error_category is not None:
            error_counts[error_category] += 1
        boolean_metrics = [
            ("answer_exact", answer_exact),
            ("canonical_exact", canonical_exact),
            ("marker_exact", marker_exact),
            ("false_acceptance", false_acceptance),
            ("safe_rejection", safe_rejection),
            ("system_answer_exact", system_answer_exact),
        ]
        if not marker_reference:
            boolean_metrics[:0] = [("parse", parse_ok), ("execution", execution_ok)]
        for name, value in boolean_metrics:
            totals[name] += int(value)
            scope_counts[name] += int(value)
            for group_name, group_values in groups.items():
                for group_value in group_values:
                    grouped[group_name][group_value][name] += int(value)
        for name, value in (
            ("result_precision", result_precision),
            ("result_recall", result_recall),
            ("result_f1", result_f1),
        ):
            totals[name] += value
            scope_counts[name] += value
            for group_name, group_values in groups.items():
                for group_value in group_values:
                    grouped[group_name][group_value][name] += value

        if include_cases:
            cases.append(
                {
                    "id": example["id"],
                    "query_id": query_id,
                    "register": register,
                    "query_features": query_features,
                    "input": example["input"],
                    "target": target,
                    "prediction": prediction,
                    "parse": parse_ok,
                    "execution": execution_ok,
                    "answer_exact": answer_exact,
                    "result_precision": result_precision,
                    "result_recall": result_recall,
                    "result_f1": result_f1,
                    "canonical_exact": canonical_exact,
                    "marker_exact": marker_exact,
                    "false_acceptance": false_acceptance,
                    "safe_rejection": safe_rejection,
                    "system_answer_exact": system_answer_exact,
                    "evaluation_group": evaluation_group,
                    "predicted_query_id": predicted_query_id,
                    "expected_slots": expected_slots,
                    "predicted_slots": predicted_slots,
                    "expected_nodes": list(expected_nodes),
                    "predicted_nodes": list(predicted_nodes),
                    "node_selection_correct": node_correct,
                    "query_shape_correct": shape_correct,
                    "rejection_decision_correct": rejection_correct,
                    "error": error,
                    "error_category": error_category,
                    "predicted_rows": predicted_rows,
                }
            )

    report = {
        "metric_policy": {
            "primary": [
                "node_selection",
                "query_shape",
                "rejection_decision",
            ],
            "composite_score": None,
            "result_set_metrics_are_diagnostic_only": True,
        },
        "primary_metrics": {
            name: _primary_rate(counts) for name, counts in primary.items()
        },
        "coverage_accounting": _coverage_accounting(accounting),
        "overall": _rates(totals),
        "in_domain": _rates(in_domain),
        "out_of_domain": _rates(out_of_domain),
        "by_register": _group_rates(grouped["register"]),
        "by_query_feature": _group_rates(grouped["query_feature"]),
        "by_query_id": _group_rates(grouped["query_id"]),
        "by_domain": _group_rates(grouped["domain"]),
        "by_anchor_kind": _group_rates(grouped["anchor_kind"]),
        "error_counts": dict(sorted(error_counts.items())),
    }
    if include_cases:
        report["cases"] = cases
    return report


def evaluate_query_id_expectations(
    expectations: list[dict[str, str]],
    predictions: Iterable[str],
    *,
    catalogue: Mapping[str, QuerySpec] | None = None,
    include_cases: bool = False,
) -> dict[str, Any]:
    """Chấm riêng các câu người thật chỉ có oracle ở mức ``query_id``.

    Tệp người thật không khai node hoặc target SPARQL nên không được trộn vào ba
    mẫu số của benchmark sinh. Query sai cú pháp và query ngoài catalogue đều
    nhận ``predicted_query_id = None`` và luôn sai.
    """

    predictions = list(predictions)
    if len(expectations) != len(predictions):
        raise ValueError("expectations and predictions must have the same length")
    catalogue = catalogue or load_catalogue(QUERY_CATALOGUE_PATH)
    correct = 0
    cases = []
    by_expected: dict[str, Counter[str]] = defaultdict(Counter)
    for index, (item, prediction) in enumerate(
        zip(expectations, predictions, strict=True),
        start=1,
    ):
        expected_query_id = item["expected_query_id"]
        normalized = prediction.strip()
        syntax_valid = False
        if normalized == _NO_INFORMATION:
            predicted_query_id = "no-information"
        else:
            try:
                validate_select(normalized)
                syntax_valid = True
            except SparqlError:
                predicted_query_id = None
            else:
                predicted_query_id, _ = _match_catalogue(catalogue, normalized)
        item_correct = predicted_query_id == expected_query_id
        correct += int(item_correct)
        by_expected[expected_query_id]["count"] += 1
        by_expected[expected_query_id]["correct"] += int(item_correct)
        if include_cases:
            cases.append(
                {
                    "id": f"real-user-{index:03d}",
                    "question": item["question"],
                    "expected_query_id": expected_query_id,
                    "prediction": prediction,
                    "predicted_query_id": predicted_query_id,
                    "syntax_valid": syntax_valid,
                    "correct": item_correct,
                }
            )
    report: dict[str, Any] = {
        "count": len(expectations),
        "correct": correct,
        "query_id_accuracy": correct / len(expectations) if expectations else 0.0,
        "by_expected_query_id": {
            query_id: _primary_rate(counts)
            for query_id, counts in sorted(by_expected.items())
        },
        "mixed_into_generated_benchmark": False,
    }
    if include_cases:
        report["cases"] = cases
    return report


def _match_catalogue(
    catalogue: Mapping[str, QuerySpec],
    query: str,
) -> tuple[str | None, dict[str, str]]:
    for query_id, spec in catalogue.items():
        if spec.domain == "out-of-domain":
            continue
        slots = match_target(spec, query)
        if slots is not None:
            return query_id, slots
    return None, {}


def _query_anchor_nodes(query: str, graph: Graph) -> tuple[str, ...]:
    """Lấy tập node neo tường minh, không phụ thuộc cách viết SPARQL.

    Bộ phân tích cú pháp RDFLib làm cho phép đo không phụ thuộc tên biến, thứ tự
    nhánh, hay việc neo bằng ``BIND``, ``VALUES`` hoặc một triple trực tiếp.
    Predicate và class là từ vựng của shape nên bị loại; các IRI cá thể/bảng còn
    lại là node được chọn. Một query chỉ tìm node gián tiếp bằng nhãn không có
    neo tường minh và vì thế không đạt hợp đồng "chọn node" của hệ thống này.
    """

    parsed = parseQuery(PREFIXES + query)
    terms: set[URIRef] = set()
    _collect_project_iris(parsed, terms)
    schema_terms = set(graph.predicates()) | set(graph.objects(predicate=RDF.type))
    return tuple(
        sorted(
            str(term).rsplit("#", 1)[-1]
            for term in terms
            if str(term).startswith(ONTOLOGY_NS)
            and str(term) != ONTOLOGY_NS
            and term not in schema_terms
        )
    )


def _collect_project_iris(value: object, found: set[URIRef]) -> None:
    if isinstance(value, URIRef):
        found.add(value)
        return
    if isinstance(value, CompValue):
        if value.name == "pname":
            # ``CompValue.get`` is attribute-oriented and returns the key name
            # itself for a missing value; use membership explicitly here.
            prefix = value["prefix"] if "prefix" in value else ""
            local = value["localname"] if "localname" in value else None
            namespaces = {
                "": ONTOLOGY_NS,
                "rdf": str(RDF),
                "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                "skos": "http://www.w3.org/2004/02/skos/core#",
                "xsd": "http://www.w3.org/2001/XMLSchema#",
            }
            if local is not None and prefix in namespaces:
                found.add(URIRef(namespaces[prefix] + str(local)))
            return
        for child in value.values():
            _collect_project_iris(child, found)
        return
    if isinstance(value, (ParseResults, list, tuple)):
        for child in value:
            _collect_project_iris(child, found)
        return
    if isinstance(value, Mapping):
        for child in value.values():
            _collect_project_iris(child, found)


def _primary_rate(counts: Counter[str]) -> dict[str, int | float]:
    count = counts["count"]
    correct = counts["correct"]
    return {
        "count": count,
        "correct": correct,
        "rate": correct / count if count else 0.0,
    }


def _coverage_accounting(counts: Counter[str]) -> dict[str, Any]:
    groups = {
        "node_queries": {
            "count": counts["node_queries"],
            "scored_by": [
                "node_selection",
                "query_shape",
                "rejection_decision",
            ],
        },
        "out_of_domain": {
            "count": counts["out_of_domain"],
            "scored_by": ["rejection_decision"],
        },
    }
    total = sum(group["count"] for group in groups.values())
    return {
        "total": total,
        "accounted_for": total,
        "groups": groups,
    }


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

    if prediction.strip() == _NO_INFORMATION:
        return "false_rejection"
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
    """Compare returned data while ignoring arbitrary SPARQL variable names."""

    return tuple(
        sorted(
            (
                tuple(sorted((_value_key(value) for value in row.values())))
                for row in rows
            ),
            key=repr,
        )
    )


def _result_scores(
    predicted_rows: list[dict[str, object]],
    reference_rows: list[dict[str, object]],
) -> tuple[float, float, float]:
    """Score overlap between result-row multisets for one query."""

    predicted = Counter(_row_values(row) for row in predicted_rows)
    reference = Counter(_row_values(row) for row in reference_rows)
    overlap = sum((predicted & reference).values())
    precision = overlap / sum(predicted.values()) if predicted else 0.0
    recall = overlap / sum(reference.values()) if reference else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, f1


def _row_values(row: dict[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(_value_key(value) for value in row.values()))


def _value_key(value: object) -> tuple[str, str]:
    if value is None:
        return ("none", "")
    return (type(value).__name__, str(value))


def _rates(counts: Counter[str]) -> dict[str, int | float]:
    total = counts["count"]
    sparql_total = counts["sparql_count"]
    marker_total = counts["marker_count"]
    return {
        "count": total,
        "parse_rate": counts["parse"] / sparql_total if sparql_total else 0.0,
        "execution_rate": counts["execution"] / sparql_total if sparql_total else 0.0,
        "answer_exact_rate": counts["answer_exact"] / total if total else 0.0,
        "result_precision": (
            counts["result_precision"] / sparql_total if sparql_total else 0.0
        ),
        "result_recall": counts["result_recall"] / sparql_total if sparql_total else 0.0,
        "result_f1": counts["result_f1"] / sparql_total if sparql_total else 0.0,
        "canonical_query_exact_rate": counts["canonical_exact"] / total if total else 0.0,
        "marker_exact_rate": (
            counts["marker_exact"] / marker_total if marker_total else 0.0
        ),
        "false_acceptance_rate": (
            counts["false_acceptance"] / marker_total if marker_total else 0.0
        ),
        "safe_rejection_rate": (
            counts["safe_rejection"] / marker_total if marker_total else 0.0
        ),
        "system_answer_exact_rate": (
            counts["system_answer_exact"] / total if total else 0.0
        ),
    }


def _group_rates(groups: dict[str, Counter[str]]) -> dict[str, dict[str, int | float]]:
    return {name: _rates(counts) for name, counts in sorted(groups.items())}
