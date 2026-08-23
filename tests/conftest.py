"""Giữ lại phần việc đắt của bộ kiểm mà không đổi kết quả của nó.

Bộ kiểm này dồn gần hết thời gian vào đúng một việc, lặp đi lặp lại: nạp ontology
chuẩn rồi chạy chừng một nghìn truy vấn của tập dữ liệu qua nó. Khoảng mười phép
kiểm khác nhau cùng làm việc ấy, và mỗi phép bắt đầu lại từ số không.

Lặp lại như vậy không học thêm được gì. Đồ thị đứng yên suốt một phiên kiểm -
không phép kiểm nào ghi vào nó - và một truy vấn SELECT trên đồ thị đứng yên luôn
trả về cùng kết quả. Chính mã sản phẩm cũng đã dựa trên lập luận đó để khử trùng
lặp bên trong một lần chạy; ở đây chỉ nới phạm vi ra cả phiên kiểm.

Khoá là **mã băm nội dung tệp ontology**, không phải đường dẫn và cũng không phải
danh tính đối tượng. Nội dung khác thì khoá khác, nên không bao giờ có chuyện lấy
kết quả của đồ thị này dùng cho đồ thị kia. Đường dẫn thì không đủ: mấy phép kiểm
chép ontology sang thư mục tạm sẽ nhận khoá riêng dù nội dung giống hệt, và mất
đúng phần tiết kiệm lớn nhất. Danh tính đối tượng cũng không đủ: số định danh của
một đối tượng đã bị thu hồi có thể được cấp lại cho đối tượng khác.

``test_shared_cache.py`` canh chính phần này. Một bộ kiểm nhớ nhầm thì vẫn xanh
nhưng không còn chứng minh điều gì, và đó là kiểu hỏng khó nhận ra nhất.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ontchatbot.runtime import sparql as _sparql

#: Mã băm nội dung → đồ thị đã nạp. Giữ tham chiếu thật ở đây, nhờ vậy số định
#: danh của đồ thị không bị thu hồi rồi cấp lại cho đối tượng khác.
_GRAPHS: dict[str, object] = {}
#: Số định danh đồ thị → mã băm nội dung của nó.
_KEY_OF_GRAPH: dict[int, str] = {}
#: (mã băm, truy vấn, trần số dòng) → các dòng lấy về.
_ROWS: dict[tuple[str, str, int], list[dict]] = {}

_load_ontology = _sparql.load_ontology
_execute_select = _sparql.execute_select


def _cached_load_ontology(path: Path = _sparql.ONTOLOGY_PATH):
    key = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    graph = _GRAPHS.get(key)
    if graph is None:
        graph = _GRAPHS[key] = _load_ontology(path)
        _KEY_OF_GRAPH[id(graph)] = key
    return graph


def _cached_execute_select(graph, query: str, *, max_rows: int = 100):
    key = _KEY_OF_GRAPH.get(id(graph))
    if key is None:
        # Đồ thị dựng tay trong một phép kiểm: không có nội dung tệp để làm khoá,
        # nên đi thẳng. Đây là các đồ thị nhỏ, chạy lại không tốn gì.
        return _execute_select(graph, query, max_rows=max_rows)
    rows = _ROWS.get((key, query, max_rows))
    if rows is None:
        rows = _ROWS[(key, query, max_rows)] = _execute_select(
            graph, query, max_rows=max_rows
        )
    # Trả bản sao: người gọi sắp xếp hoặc sửa tại chỗ thì không được đụng tới bản
    # đang giữ, nếu không phép kiểm chạy sau nhận dữ liệu đã bị phép kiểm trước
    # bóp méo. Các ô đều là giá trị nguyên thuỷ nên sao một tầng là đủ.
    return [dict(row) for row in rows]


# Để phép kiểm canh đối chiếu được với bản gốc mà không phải nạp lại tệp này.
_cached_load_ontology.uncached = _load_ontology
_cached_execute_select.uncached = _execute_select

# Thay ngay lúc nạp tệp này. pytest nạp ``conftest.py`` trước mọi tệp kiểm, nên
# các ``from ... import load_ontology`` sau đó đều lấy đúng bản có nhớ đệm.
#
# Chốt chống nạp hai lần: nếu tệp này chạy lần nữa thì ``_load_ontology`` ở trên
# sẽ trỏ vào chính lớp bọc, và lớp bọc gọi chính nó là đệ quy vô hạn. Rẻ để đặt,
# và kiểu hỏng nó chặn thì rất khó đọc ra từ vết lỗi.
if not hasattr(_load_ontology, "uncached"):
    _sparql.load_ontology = _cached_load_ontology
    _sparql.execute_select = _cached_execute_select
