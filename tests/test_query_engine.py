from __future__ import annotations

import pytest
from rdflib import URIRef

from ontchatbot.query_engine import SparqlError, execute_select, load_ontology, validate_select


@pytest.fixture(scope="module")
def graph():
    return load_ontology()


def test_direct_datatype_query(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }",
    )

    assert len(rows) == 1
    assert "bảo lưu kết quả" in rows[0]["answer"]


def test_repeated_condition_literals(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :condition ?answer . }",
    )

    assert len(rows) == 4
    assert {row["answer"] for row in rows} >= {
        "Được điều động vào lực lượng vũ trang",
        "Vì lý do cá nhân khác nhưng phải học ít nhất 01 học kỳ ở Trường",
    }


def test_object_hop_projects_label(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?office . "
        "?office rdfs:label ?answer . }",
    )

    assert rows == [{"answer": "Phòng Công tác Sinh viên"}]


def test_object_hop_projects_datatype(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?office . "
        "?office :email ?answer . }",
    )

    assert rows == [{"answer": "ctsv@ntu.edu.vn"}]


def test_multiple_columns_preserve_pairing(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?document ?url WHERE { :AcademicLeaveProcedure :hasDocument ?node . "
        "?node rdfs:label ?document ; :documentUrl ?url . }",
    )

    assert len(rows) == 2
    assert all(set(row) == {"document", "url"} for row in rows)
    assert all(row["url"].startswith("https://") for row in rows)


def test_filter_and_typed_number(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { ?rate a :TuitionRate ; :cohortCode ?cohort ; "
        ":programName ?program ; :tuitionPerCredit ?answer . "
        'FILTER ( STR ( ?cohort ) = "K63" ) '
        'FILTER ( STR ( ?program ) = "Công nghệ sinh học" ) }',
    )

    assert rows == [{"answer": 600000}]


def test_aggregate(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT (COUNT(DISTINCT ?method) AS ?answer) WHERE { "
        ":TuitionPaymentProcedure :supportsPaymentMethod ?method . }",
    )

    assert rows == [{"answer": 2}]


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("", "empty"),
        ("ASK { ?s ?p ?o }", "only SELECT"),
        ("SELECT * WHERE { ?s ?p ?o . }", r"SELECT \*"),
        ("PREFIX bad: <https://example.com/> SELECT ?x WHERE { ?x ?p ?o . }", "only SELECT"),
        ("SELECT ?x WHERE { SERVICE <https://example.com/> { ?x ?p ?o } }", "SERVICE"),
        ("SELECT ?x FROM <https://example.com/> WHERE { ?x ?p ?o . }", "FROM"),
        ("SELECT ?answer WHERE {", "invalid SPARQL"),
    ],
)
def test_rejects_queries_outside_contract(query: str, message: str) -> None:
    with pytest.raises(SparqlError, match=message):
        validate_select(query)


def test_rejects_graph_nodes_in_projection(graph) -> None:
    with pytest.raises(SparqlError, match="graph node"):
        execute_select(
            graph,
            "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?answer . }",
        )


def test_accepts_multiline_select(graph) -> None:
    rows = execute_select(
        graph,
        """SELECT ?answer WHERE {
            :AcademicLeaveProcedure :handledBy ?office .
            ?office rdfs:label ?answer .
        }""",
    )

    assert rows == [{"answer": "Phòng Công tác Sinh viên"}]


def test_result_values_never_expose_uris(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { ?procedure a :AcademicProcedure ; rdfs:label ?answer . }",
    )

    assert rows
    assert all(not isinstance(value, URIRef) for row in rows for value in row.values())
