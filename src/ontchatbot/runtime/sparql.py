"""Chạy SPARQL chỉ-đọc trên ontology chuẩn, cho đường phục vụ.

Đồ thị nằm trong kho Oxigraph. Module này không nhập rdflib ở bất kỳ đâu, kể cả
trong thân hàm: tạo một đồ thị rdflib kéo theo bộ phân tích SPARQL viết bằng
pyparsing, mà bộ ấy dựng cả bộ văn phạm ngay lúc nạp thư viện - chi phí đó rơi vào
mỗi lần khởi động nguội, cho một việc Oxigraph vẫn tự làm.

Các công cụ ngoại tuyến cần API duyệt bộ ba của rdflib thì dùng ``research.graph``.
Nó gọi lại ``check_select_contract`` và ``from_lexical`` ở đây, nên hợp đồng câu
truy vấn và phép đổi literal chỉ có một bản cài đặt.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TypeAlias

import pyoxigraph as ox

from ..settings import ONTOLOGY_NS, ONTOLOGY_PATH

Primitive: TypeAlias = str | int | float | bool | None
QueryRow: TypeAlias = dict[str, Primitive]
QueryRows: TypeAlias = list[QueryRow]

PREFIXES = f"""\
PREFIX : <{ONTOLOGY_NS}>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

MAX_QUERY_CHARS = 4096
SOURCE_CITATION = ox.NamedNode(ONTOLOGY_NS + "sourceCitation")
SOURCE_LINK = ox.NamedNode(ONTOLOGY_NS + "sourceLink")
#: Nêu bằng IRI dạng chuỗi để dùng được với cả hai lối biểu diễn đồ thị.
SOURCE_PROJECTION_IRIS = frozenset(
    (ONTOLOGY_NS + "sourceCitation", ONTOLOGY_NS + "sourceLink")
)
_BASED_ON = ox.NamedNode(ONTOLOGY_NS + "basedOn")
_CITATION_LABEL = ox.NamedNode(ONTOLOGY_NS + "citationLabel")
_DOCUMENT_URL = ox.NamedNode(ONTOLOGY_NS + "documentUrl")
_WEB_PAGE_URL = ox.NamedNode(ONTOLOGY_NS + "webPageUrl")

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(?:SERVICE|FROM|INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD|WITH)\b",
    flags=re.IGNORECASE,
)
_XSD = "http://www.w3.org/2001/XMLSchema#"
_RDF_LANGSTRING = "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"
#: Kiểu trả về nguyên văn phần chữ của literal.
_TEXT_DATATYPES = frozenset(
    {None, _RDF_LANGSTRING}
    | {
        _XSD + name
        for name in (
            "string",
            "anyURI",
            "normalizedString",
            "token",
            "language",
            "NMTOKEN",
            "Name",
            "NCName",
        )
    }
)
_INTEGER_DATATYPES = frozenset(
    _XSD + name
    for name in (
        "integer",
        "int",
        "long",
        "short",
        "byte",
        "nonNegativeInteger",
        "positiveInteger",
        "nonPositiveInteger",
        "negativeInteger",
        "unsignedInt",
        "unsignedLong",
        "unsignedShort",
        "unsignedByte",
    )
)
_FLOAT_DATATYPES = frozenset((_XSD + "double", _XSD + "float"))


class SparqlError(ValueError):
    """The generated query violates the runtime contract or cannot execute."""


def load_ontology(path: Path = ONTOLOGY_PATH) -> ox.Store:
    """Load the canonical Turtle ontology and its compact source view."""

    store = ox.Store()
    with open(path, "rb") as handle:
        parser = ox.parse(handle, format=ox.RdfFormat.TURTLE)
        store.bulk_extend(
            ox.Quad(triple.subject, triple.predicate, triple.object)
            for triple in parser
        )
        # Prefix chỉ đầy đủ sau khi bộ sinh ở trên đã bị duyệt cạn.
        declared = parser.prefixes.get("")
    if declared != ONTOLOGY_NS:
        # ``ValueError`` chứ không phải ``SparqlError``: tệp ontology sai, không
        # phải câu truy vấn sai. Người gọi bắt ``SparqlError`` rồi đổi thành
        # "không có kết quả", nên lỗi này sẽ biến mất trong im lặng.
        raise ValueError(
            f"ontology khai prefix mặc định ':' là {declared!r}, chờ {ONTOLOGY_NS!r}"
        )
    _add_source_projection(store)
    return store


def _objects(store: ox.Store, subject, predicate) -> list:
    return [quad.object for quad in store.quads_for_pattern(subject, predicate, None)]


def _add_source_projection(store: ox.Store) -> None:
    """Materialize one compact, paired source record for every answer anchor.

    Canonical queries emit the two project source fields rather than repeating
    a long source subquery. The projection is a runtime view: both
    ``documentUrl`` and ``webPageUrl`` normalize here, and an empty string keeps
    an absent member of a citation/URL pair.
    """

    subjects = sorted(
        {quad.subject for quad in store if isinstance(quad.subject, ox.NamedNode)},
        key=lambda node: node.value,
    )
    for subject in subjects:
        source_nodes = sorted(
            {
                node
                for node in _objects(store, subject, _BASED_ON)
                if isinstance(node, ox.NamedNode)
            },
            key=lambda node: node.value,
        ) or [subject]
        pairs: list[tuple[str, str]] = []
        for source in source_nodes:
            citations = sorted(
                value.value
                for value in _objects(store, source, _CITATION_LABEL)
                if isinstance(value, ox.Literal)
            )
            urls = sorted(
                value.value
                for predicate in (_DOCUMENT_URL, _WEB_PAGE_URL)
                for value in _objects(store, source, predicate)
                if isinstance(value, ox.Literal)
            )
            if citations or urls:
                pairs.extend(
                    (citation, url)
                    for citation in (citations or [""])
                    for url in (urls or [""])
                )
        if pairs:
            store.add(
                ox.Quad(
                    subject,
                    SOURCE_CITATION,
                    ox.Literal(" · ".join(citation for citation, _ in pairs)),
                )
            )
            store.add(
                ox.Quad(
                    subject,
                    SOURCE_LINK,
                    ox.Literal(" · ".join(url for _, url in pairs)),
                )
            )


def check_select_contract(query: str) -> str:
    """Chốt hình dạng câu truy vấn bằng vài phép so khớp, không phân tích cú pháp.

    Bước chạy tự phát hiện lỗi cú pháp, nên ``execute_select`` chỉ cần tới đây.
    Kiểm cú pháp riêng là ``research.graph.validate_select``, dành cho SPARQL đến
    từ ngoài danh mục.
    """

    if not isinstance(query, str):
        raise SparqlError("SPARQL query must be text")

    query = query.strip()
    if not query:
        raise SparqlError("SPARQL query is empty")
    if len(query) > MAX_QUERY_CHARS:
        raise SparqlError(f"SPARQL query exceeds {MAX_QUERY_CHARS} characters")
    if not re.match(r"^SELECT\b", query, flags=re.IGNORECASE):
        raise SparqlError("only SELECT queries are allowed")
    if re.match(r"^SELECT\s+\*", query, flags=re.IGNORECASE):
        raise SparqlError("SELECT * is not allowed; project explicit answer columns")

    forbidden = _FORBIDDEN_KEYWORDS.search(query)
    if forbidden:
        raise SparqlError(f"SPARQL keyword is not allowed: {forbidden.group(0).upper()}")

    return query


def execute_select(store: ox.Store, query: str, *, max_rows: int = 100) -> QueryRows:
    """Run a validated SELECT and return only plain Python mappings."""

    if max_rows < 1:
        raise ValueError("max_rows must be positive")

    query = check_select_contract(query)
    try:
        solutions = store.query(PREFIXES + query)
    except Exception as exc:
        raise SparqlError(f"SPARQL execution failed: {exc}") from exc

    columns = [variable.value for variable in solutions.variables]
    if not columns:
        raise SparqlError("SELECT query has no result columns")

    rows: QueryRows = []
    for row_number, solution in enumerate(solutions, start=1):
        if row_number > max_rows:
            raise SparqlError(f"SPARQL result exceeds {max_rows} rows")
        rows.append(
            {
                column: _to_primitive(solution[index], column)
                for index, column in enumerate(columns)
            }
        )
    return rows


def _to_primitive(term, column: str) -> Primitive:
    if term is None:
        return None
    if isinstance(term, (ox.NamedNode, ox.BlankNode)):
        raise SparqlError(
            f"result column ?{column} contains a graph node; project rdfs:label or a literal"
        )
    if not isinstance(term, ox.Literal):
        raise SparqlError(f"result column ?{column} is not an RDF literal")
    datatype = term.datatype.value if term.datatype is not None else None
    return from_lexical(term.value, datatype)


def from_lexical(text: str, datatype: str | None) -> Primitive:
    """Đổi phần chữ của literal thành giá trị Python theo kiểu XSD của nó.

    Kiểu lạ thì giữ nguyên phần chữ, vì đoán một phép đổi sẽ tạo ra con số mà
    đồ thị không hề khẳng định.
    """

    if datatype in _TEXT_DATATYPES:
        return text
    if datatype in _INTEGER_DATATYPES:
        try:
            return int(text)
        except ValueError:
            return text
    if datatype == _XSD + "boolean":
        return text in ("true", "1")
    if datatype in _FLOAT_DATATYPES:
        try:
            return float(text)
        except ValueError:
            return text
    if datatype == _XSD + "decimal":
        # ``xsd:decimal`` giữ nguyên số chữ số thập phân đã ghi, nên sĩ số 20
        # được ghi là "20.0" sẽ hiện ra thành 20 chứ không phải "20.0".
        try:
            number = Decimal(text)
        except InvalidOperation:
            return text
        return int(number) if number == number.to_integral_value() else float(number)
    return text
