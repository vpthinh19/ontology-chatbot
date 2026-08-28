"""Đọc ontology và chạy SPARQL bằng rdflib, cho các công cụ ngoại tuyến.

Chúng cần API duyệt bộ ba của rdflib, thứ kho Oxigraph không có, và chúng chạy
lúc dựng dữ liệu hoặc lúc chấm điểm nên chi phí nạp thư viện không đáng kể. Đường
phục vụ thì ngược lại, và nó ở ``runtime.sparql``.

Hợp đồng câu truy vấn và phép đổi literal lấy thẳng từ đó chứ không chép lại: hai
bản sẽ lệch nhau lúc nào không hay, và khi ấy bộ chấm chấm trên thứ khác với thứ
đang phục vụ.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from threading import Lock

from ..runtime.sparql import (
    PREFIXES,
    SOURCE_CITATION,
    SOURCE_LINK,
    QueryRow,
    QueryRows,
    SparqlError,
    check_select_contract,
    from_lexical,
)
from ..runtime.sparql import load_ontology as load_store
from ..settings import ONTOLOGY_PATH

#: Bộ phân tích của rdflib dùng chung trạng thái văn phạm giữa các lần gọi, nên
#: chỉ một luồng được vào.
_PARSE_LOCK = Lock()


def load_ontology(path: Path = ONTOLOGY_PATH):
    """Ontology dưới dạng đồ thị rdflib, kèm đúng phép chiếu nguồn của bản phục vụ.

    Phép chiếu chạy trên kho Oxigraph và chỉ có một bản cài đặt; ở đây chỉ chép
    sang các bộ ba nó sinh ra.

    Đồ thị đọc thẳng từ Turtle chứ không dựng lại từ kho: truy vấn không có
    ``ORDER BY`` lấy thứ tự nội bộ của kho, mà thứ tự ấy phụ thuộc cách nạp, nên
    dựng lại sẽ xáo thứ tự dòng của mọi kết quả ngoại tuyến.
    """

    from rdflib import Graph, Literal, URIRef

    store = load_store(path)
    graph = Graph(store="Oxigraph").parse(Path(path), format="turtle")
    for predicate in (SOURCE_CITATION, SOURCE_LINK):
        for quad in store.quads_for_pattern(None, predicate, None):
            graph.add(
                (
                    URIRef(quad.subject.value),
                    URIRef(predicate.value),
                    Literal(quad.object.value),
                )
            )
    return graph


def validate_select(query: str) -> str:
    """Kiểm cú pháp một câu truy vấn do model sinh, không cố sửa nó.

    Dành cho SPARQL đến từ ngoài danh mục. ``execute_select`` không gọi hàm này:
    bước chạy đã phân tích câu truy vấn, nên gọi cả hai là phân tích hai lần.
    """

    query = check_select_contract(query)
    _parse_select(query)
    return query


@lru_cache(maxsize=4096)
def _parse_select(query: str) -> None:
    """Phân tích cú pháp bằng bộ phân tích của rdflib.

    Không dùng ``Store.query`` của Oxigraph: hàm đó còn lập kế hoạch thực thi, và
    giá lập kế hoạch tăng vọt theo số mẫu đồ thị - một câu dài vẫn lọt trần
    ``MAX_QUERY_CHARS`` có thể tốn hàng chục giây ở đó.

    Bộ phân tích nhận cả ASK, CONSTRUCT và DESCRIBE, nên chốt ``^SELECT`` trong
    ``check_select_contract`` phải chạy trước.

    ``lru_cache`` không nhớ ngoại lệ, nên câu sai vẫn bị báo lỗi mỗi lần.
    """

    from rdflib.plugins.sparql.parser import parseQuery

    try:
        with _PARSE_LOCK:
            parseQuery(PREFIXES + query)
    except Exception as exc:  # rdflib để lộ ngoại lệ của chính bộ phân tích.
        raise SparqlError(f"invalid SPARQL: {exc}") from exc


def execute_select(graph, query: str, *, max_rows: int = 100) -> QueryRows:
    """Chạy một SELECT trên đồ thị rdflib, trả về đúng thứ bản phục vụ trả về.

    Cùng hình dạng với ``runtime.sparql.execute_select``: chỉ giá trị Python
    thuần, cùng thứ tự cột, cùng phép đổi literal.
    """

    from rdflib import BNode, Literal, URIRef

    if max_rows < 1:
        raise ValueError("max_rows must be positive")

    query = check_select_contract(query)
    try:
        result = graph.query(PREFIXES + query)
    except Exception as exc:
        raise SparqlError(f"SPARQL execution failed: {exc}") from exc

    columns = [str(variable) for variable in result.vars or ()]
    if not columns:
        raise SparqlError("SELECT query has no result columns")

    rows: QueryRows = []
    for row_number, row in enumerate(result, start=1):
        if row_number > max_rows:
            raise SparqlError(f"SPARQL result exceeds {max_rows} rows")
        row_values: QueryRow = {}
        for index, column in enumerate(columns):
            value = row[index]
            if value is None:
                row_values[column] = None
            elif isinstance(value, (URIRef, BNode)):
                raise SparqlError(
                    f"result column ?{column} contains a graph node; "
                    "project rdfs:label or a literal"
                )
            elif not isinstance(value, Literal):
                raise SparqlError(f"result column ?{column} is not an RDF literal")
            else:
                # ``str`` của một literal rdflib là phần chữ nguyên văn; thuộc
                # tính ``value`` thì đã là giá trị Python đã đổi kiểu sẵn.
                row_values[column] = from_lexical(
                    str(value),
                    str(value.datatype) if value.datatype is not None else None,
                )
        rows.append(row_values)
    return rows
