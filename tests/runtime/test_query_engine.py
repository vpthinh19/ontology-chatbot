from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pyoxigraph
import pytest
from rdflib import Graph, URIRef

from ontchatbot.research.graph import execute_select as execute_on_rdflib
from ontchatbot.research.graph import validate_select
from ontchatbot.runtime.sparql import SparqlError, load_ontology
from ontchatbot.runtime.sparql import execute_select as execute_on_store
from ontchatbot.settings import ONTOLOGY_NS


FIXTURE_TURTLE = f"""
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
        """


def execute_select(graph, query: str, **kwargs):
    """Gửi truy vấn tới bộ chạy ứng với kiểu đồ thị đang được kiểm.

    Phép rẽ nhánh này nằm ở đây chứ không nằm trong mã sản phẩm: đường phục vụ
    chỉ biết kho Oxigraph, các công cụ ngoại tuyến chỉ biết đồ thị rdflib. Chính
    tệp kiểm này là chỗ duy nhất cần cả hai, vì việc của nó là chứng minh hai bên
    trả về y hệt nhau.
    """

    if isinstance(graph, pyoxigraph.Store):
        return execute_on_store(graph, query, **kwargs)
    return execute_on_rdflib(graph, query, **kwargs)


@pytest.fixture(scope="module", params=["oxigraph", "rdflib"])
def graph(request):
    """Cùng dữ liệu ấy dưới cả hai lối biểu diễn đồ thị.

    Đường phục vụ đọc kho Oxigraph, các công cụ ngoại tuyến đọc đồ thị rdflib, và
    hai bên phải trả về y hệt nhau: cùng số dòng, cùng thứ tự, cùng kiểu Python.
    Chạy trọn bộ khẳng định của tệp này qua cả hai lối là cách canh điều đó -
    một lối lặng lẽ đổi cách bóc literal thì phép kiểm đỏ ngay.
    """

    if request.param == "rdflib":
        return Graph(store="Oxigraph").parse(data=FIXTURE_TURTLE, format="turtle")
    store = pyoxigraph.Store()
    store.load(FIXTURE_TURTLE, format=pyoxigraph.RdfFormat.TURTLE)
    return store


def test_concurrent_cold_valid_queries_stay_valid() -> None:
    """Xác thực nhiều truy vấn lạ cùng lúc phải cho cùng kết quả với chạy lẻ."""
    worker_count = 8
    queries = [
        "SELECT ?answer WHERE { :ExampleRecord :text ?answer . "
        f'FILTER ( "cold-{index}" = "cold-{index}" ) }}'
        for index in range(64)
    ]
    barrier = threading.Barrier(worker_count)

    def validate_partition(worker: int) -> list[str]:
        barrier.wait()
        return [validate_select(query) for query in queries[worker::worker_count]]

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        partitions = list(pool.map(validate_partition, range(worker_count)))

    validated = [query for partition in partitions for query in partition]
    assert sorted(validated) == sorted(queries)


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
    """Khuôn nguồn rút gọn phải giữ cả trích dẫn và đường dẫn.

    ``COALESCE`` chỉ dùng giá trị dự phòng khi biến chưa được gán, không thay thế
    chuỗi rỗng. Vì vậy mọi cặp nguồn phải có ``citationLabel`` không rỗng và URL
    để các điều khoản kế thừa nguồn văn bản vẫn hiển thị đủ thông tin.
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

    # Kiểm tra toàn bộ lớp node có nguồn để mọi lần nạp văn bản đều giữ trích dẫn.
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


def test_literal_conversion_matches_rdflib_on_every_literal_in_the_ontology() -> None:
    """Chỗ hai lối dễ lệch nhất là bóc literal, nên kiểm vét cạn đúng chỗ đó.

    rdflib đổi kiểu bằng ``toPython`` của chính nó; Oxigraph không có phép ấy nên
    lối mới đọc kiểu XSD rồi tự đổi. Phép kiểm này lấy rdflib làm mốc và đối chiếu
    TỪNG literal trong ontology - vét cạn mà vẫn nhanh, vì không chạy truy vấn nào.
    """

    from decimal import Decimal

    from rdflib import Literal as RdflibLiteral

    from ontchatbot.research.graph import load_ontology as load_rdflib_graph
    from ontchatbot.runtime.sparql import from_lexical

    def rdflib_reference(literal):
        """Đúng phép đổi mà lối rdflib vẫn dùng trước khi có Oxigraph."""

        converted = literal.toPython()
        if converted is None or isinstance(converted, (str, int, float, bool)):
            return converted
        if isinstance(converted, Decimal):
            integral = converted == converted.to_integral_value()
            return int(converted) if integral else float(converted)
        return str(converted)

    graph = load_rdflib_graph()
    checked = 0
    datatypes = set()
    for _subject, _predicate, value in graph:
        if not isinstance(value, RdflibLiteral):
            continue
        checked += 1
        datatypes.add(str(value.datatype) if value.datatype is not None else None)
        expected = rdflib_reference(value)
        datatype = str(value.datatype) if value.datatype is not None else None
        actual = from_lexical(str(value), datatype)
        assert actual == expected, (str(value), datatype, actual, expected)
        assert type(actual) is type(expected), (str(value), datatype)

    assert checked > 4000, f"chỉ soi được {checked} literal"
    # Ontology mọc thêm một kiểu XSD lạ thì phép kiểm này phải được nhìn lại,
    # chứ không lặng lẽ bỏ qua kiểu đó.
    assert datatypes == {
        None,
        "http://www.w3.org/2001/XMLSchema#anyURI",
        "http://www.w3.org/2001/XMLSchema#date",
        "http://www.w3.org/2001/XMLSchema#decimal",
        "http://www.w3.org/2001/XMLSchema#integer",
        "http://www.w3.org/2001/XMLSchema#string",
    }, sorted(str(item) for item in datatypes)


def test_both_engines_agree_on_the_real_catalogue_queries() -> None:
    """Truy vấn thật, dữ liệu thật: hai lối phải trả cùng dòng, cùng thứ tự.

    Phép kiểm trên đã vét cạn phần bóc literal, nên ở đây chỉ cần canh phần còn
    lại - số dòng, thứ tự dòng và thứ tự cột. Lấy thưa cho gọn: các câu truy vấn
    dùng chung một nhúm khuôn, nên một mẫu thưa vẫn chạm mọi khuôn.
    """

    from ontchatbot.research.graph import load_ontology as load_rdflib_graph
    from ontchatbot.runtime.cards import build_cards

    store = load_ontology()
    graph = load_rdflib_graph()
    queries = [
        card.query
        for card in build_cards(store)
        if card.query.strip().upper().startswith("SELECT")
    ]
    assert len(queries) > 300

    for query in queries[::12]:
        assert execute_on_store(store, query) == execute_on_rdflib(graph, query), query
