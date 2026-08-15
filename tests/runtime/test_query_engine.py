from __future__ import annotations

import pytest
from rdflib import Graph, URIRef

from ontchatbot.runtime.sparql import (
    SparqlError,
    execute_select,
    load_ontology,
    validate_select,
)
from ontchatbot.settings import ONTOLOGY_NS


@pytest.fixture(scope="module")
def graph():
    return Graph(store="Oxigraph").parse(
        data=f"""
            @prefix : <{ONTOLOGY_NS}> .
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

            :ExampleRecord a :ExampleType ;
                :text "Nội dung mẫu"@vi ;
                :tag "Nhãn một"@vi, "Nhãn hai"@vi ;
                :related :ExampleNode ;
                :hasDocument :DocumentA, :DocumentB ;
                :supportsMethod :MethodA, :MethodB .
            :ExampleNode rdfs:label "Nút liên quan"@vi ; :email "node@example.com" .
            :DocumentA rdfs:label "Tài liệu A"@vi ; :url "https://example.com/a"^^xsd:anyURI .
            :DocumentB rdfs:label "Tài liệu B"@vi ; :url "https://example.com/b"^^xsd:anyURI .
            :MeasuredItem :category "A" ; :amount "600000"^^xsd:nonNegativeInteger .
        """,
        format="turtle",
    )


def test_direct_datatype_query(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :ExampleRecord :text ?answer . }",
    )

    assert len(rows) == 1
    assert rows == [{"answer": "Nội dung mẫu"}]


def test_repeated_condition_literals(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :ExampleRecord :tag ?answer . } ORDER BY ?answer",
    )

    assert rows == [{"answer": "Nhãn hai"}, {"answer": "Nhãn một"}]


def test_object_hop_projects_label(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :ExampleRecord :related ?node . "
        "?node rdfs:label ?answer . }",
    )

    assert rows == [{"answer": "Nút liên quan"}]


def test_object_hop_projects_datatype(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { :ExampleRecord :related ?node . "
        "?node :email ?answer . }",
    )

    assert rows == [{"answer": "node@example.com"}]


def test_multiple_columns_preserve_pairing(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?document ?url WHERE { :ExampleRecord :hasDocument ?node . "
        "?node rdfs:label ?document ; :url ?url . }",
    )

    assert len(rows) == 2
    assert all(set(row) == {"document", "url"} for row in rows)
    assert all(row["url"].startswith("https://") for row in rows)


def test_every_source_pair_carries_a_citation_and_a_url() -> None:
    """Khuôn nguồn rút gọn phải giữ ĐỦ CẢ HAI vế: trích dẫn và đường dẫn.

    Bản trước của phép kiểm này chốt cứng rằng trang web tự trả lời về mình chỉ có
    đường dẫn, còn trích dẫn là CHUỖI RỖNG - và coi đó là hành vi đúng. Nó không
    đúng, chỉ là mô tả hiện trạng lúc ấy: 17 node văn bản chưa khai
    ``citationLabel`` cho chính mình.

    Chuỗi rỗng đó âm thầm gây hại. Khi một điều khoản mượn số hiệu hay ngày ban
    hành của văn bản mẹ, dòng đó nhận trích dẫn rỗng, và cả một mệnh đề lui trong
    truy vấn cũng không cứu được vì ``COALESCE`` chỉ lui khi biến CHƯA GÁN chứ
    không lui khi gán chuỗi rỗng. Đã khai đủ 17 trích dẫn (15/8/2026), nên nay
    mọi cặp nguồn đều đủ hai vế.
    """

    graph = load_ontology()

    organisation_rows = execute_select(
        graph,
        "SELECT ?citation ?url WHERE { :AcademicManagementUnit :sourceCitation ?citation ; :sourceLink ?url . }",
    )
    web_only_rows = execute_select(
        graph,
        "SELECT ?citation ?url WHERE { :OrganizationStructurePage :sourceCitation ?citation ; :sourceLink ?url . }",
    )

    assert organisation_rows == [
        {
            "citation": (
                "danh sách đơn vị trên trang Cơ cấu tổ chức - Khối tham mưu, "
                "quản lý của Trường Đại học Nha Trang, truy cập ngày 14/8/2026"
            ),
            "url": "https://ntu.edu.vn/co-cau-to-chuc/khoi-tham-muu-quan-ly",
        }
    ]
    assert web_only_rows == [
        {
            "citation": (
                "trang Cơ cấu tổ chức - Khối tham mưu, quản lý của Trường Đại học "
                "Nha Trang, truy cập ngày 14/8/2026"
            ),
            "url": "https://ntu.edu.vn/co-cau-to-chuc/khoi-tham-muu-quan-ly",
        }
    ]

    # Không node văn bản nào được để trống vế trích dẫn nữa - canh cả lớp, không
    # canh riêng một node, để lần nạp văn bản sau không lặng lẽ tái diễn.
    empty = execute_select(
        graph,
        "SELECT ?x WHERE { ?x :sourceCitation ?citation . FILTER(STRLEN(?citation)=0) }",
    )
    assert empty == []


def test_filter_and_typed_number(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { ?item :category ?category ; :amount ?answer . "
        'FILTER ( STR ( ?category ) = "A" ) }',
    )

    assert rows == [{"answer": 600000}]


def test_aggregate(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT (COUNT(DISTINCT ?method) AS ?answer) WHERE { "
        ":ExampleRecord :supportsMethod ?method . }",
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
            "SELECT ?answer WHERE { :ExampleRecord :related ?answer . }",
        )


def test_accepts_multiline_select(graph) -> None:
    rows = execute_select(
        graph,
        """SELECT ?answer WHERE {
            :ExampleRecord :related ?node .
            ?node rdfs:label ?answer .
        }""",
    )

    assert rows == [{"answer": "Nút liên quan"}]


def test_result_values_never_expose_uris(graph) -> None:
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { ?node rdfs:label ?answer . }",
    )

    assert rows
    assert all(not isinstance(value, URIRef) for row in rows for value in row.values())
