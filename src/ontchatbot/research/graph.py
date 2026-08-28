"""Đọc ontology và chạy SPARQL bằng rdflib, cho các công cụ ngoại tuyến.

Đường phục vụ dùng ``runtime.sparql`` và chỉ biết kho Oxigraph. Lối rdflib nằm
riêng ở đây vì một lý do đo được: chỉ *tạo* một đồ thị rdflib đã kéo theo bộ phân
tích SPARQL viết bằng pyparsing, mà bộ ấy dựng nguyên bộ văn phạm ngay lúc nạp
thư viện. Trên một nhân của nền tảng triển khai đó là 1,4 giây ở MỖI lần khởi
động nguội, cho một việc mà Oxigraph vẫn đang tự làm. Trên máy nhiều nhân thì chỉ
khoảng 0,1 giây, nên đo ở máy lập trình sẽ không thấy khoản này.

Các công cụ gọi tới đây chạy lúc dựng dữ liệu và lúc chấm điểm chứ không phục vụ
câu hỏi, nên giá nạp thư viện ở đó không đáng kể; đổi lại chúng cần API duyệt bộ
ba của rdflib, thứ mà kho Oxigraph không có.

Phần hợp đồng dùng chung - chốt hình dạng câu truy vấn, và phép đổi literal thành
giá trị Python - lấy thẳng từ ``runtime.sparql`` chứ không chép lại. Chép lại thì
hai bản phải giống nhau mãi mãi mà không gì canh, và một bên lệch đi thì bộ chấm
lặng lẽ chấm trên thứ khác với thứ đang phục vụ.
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
#: chỉ một luồng được vào. Các câu đã gặp không đi qua đây nhờ ``lru_cache``.
_PARSE_LOCK = Lock()


def load_ontology(path: Path = ONTOLOGY_PATH):
    """Ontology dưới dạng đồ thị rdflib, kèm đúng phép chiếu nguồn của bản phục vụ.

    Phép chiếu nguồn chỉ có MỘT bản cài đặt, chạy trên kho Oxigraph; ở đây chỉ
    chép sang các bộ ba mà nó sinh ra.

    Đồ thị rdflib vẫn đọc thẳng từ Turtle chứ không dựng lại từ kho. Truy vấn
    không có ``ORDER BY`` trả dòng theo thứ tự nội bộ của kho, mà thứ tự ấy phụ
    thuộc cách nạp - dựng lại từ kho sẽ đổi thứ tự dòng của mọi công cụ ngoại
    tuyến, đổi cả các tệp kết quả đã chốt, mà không đổi lấy một dữ kiện nào.
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
    """Kiểm một câu truy vấn do model sinh, không cố sửa nó.

    Dùng cho SPARQL đến từ bên ngoài danh mục - tức đường chấm điểm ngoại tuyến.
    ``execute_select`` KHÔNG gọi hàm này: nó chỉ cần chốt hình dạng, còn cú pháp
    thì bước chạy tự phát hiện, nên gọi cả hai là phân tích câu truy vấn hai lần.
    """

    query = check_select_contract(query)
    _parse_select(query)
    return query


@lru_cache(maxsize=4096)
def _parse_select(query: str) -> None:
    """Phân tích cú pháp bằng bộ phân tích của rdflib.

    Cố ý KHÔNG dùng ``Store.query`` của Oxigraph: hàm đó không chỉ phân tích mà
    còn lập kế hoạch thực thi, và giá lập kế hoạch tăng vọt theo số mẫu đồ thị.
    Một câu 4.093 ký tự vẫn lọt trần ``MAX_QUERY_CHARS`` có thể tốn gần một phút
    ở đó, trong khi phân tích cú pháp thuần mất chưa tới 200 ms.

    Chốt ``^SELECT`` nằm trong ``check_select_contract`` và phải chạy trước bước
    này, vì bộ phân tích nhận cả ASK, CONSTRUCT và DESCRIBE - nó chỉ trả lời "có
    đúng cú pháp SPARQL không".

    ``lru_cache`` không nhớ ngoại lệ, nên câu sai vẫn được phân tích lại và vẫn
    báo lỗi mỗi lần.
    """

    from rdflib.plugins.sparql.parser import parseQuery

    try:
        with _PARSE_LOCK:
            parseQuery(PREFIXES + query)
    except Exception as exc:  # rdflib để lộ ngoại lệ của chính bộ phân tích.
        raise SparqlError(f"invalid SPARQL: {exc}") from exc


def execute_select(graph, query: str, *, max_rows: int = 100) -> QueryRows:
    """Chạy một SELECT trên đồ thị rdflib, trả về đúng thứ bản phục vụ trả về.

    Cùng hình dạng dữ liệu với ``runtime.sparql.execute_select``: chỉ giá trị
    Python thuần, cùng thứ tự cột, cùng phép đổi literal. Bộ kiểm đối chiếu canh
    điều đó bằng cách chạy trọn một tệp khẳng định qua cả hai lối.
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
