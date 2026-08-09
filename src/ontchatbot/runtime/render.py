"""Generic rendering for SPARQL rows; no ontology-specific result DTOs."""

from __future__ import annotations

from .sparql import Primitive, QueryRows

NO_INFORMATION_REPLY = "Không có thông tin."

#: Tên cột trong SPARQL không chứa được dấu cách, nên chúng dính liền và nhìn
#: như lỗi khi in ra cho người dùng. Bảng này chỉ đổi CÁCH HIỂN THỊ; cột nào
#: không có trong bảng thì giữ nguyên tên, nên thêm họ truy vấn mới không vỡ.
_LABELS = {
    "ápdụngcho": "Áp dụng cho",
    "biểumẫu": "Biểu mẫu",
    "bước": "Các bước",
    "cáchgiảiquyết": "Cách giải quyết",
    "căncứ": "Căn cứ",
    "cổngthanhtoán": "Cổng thanh toán",
    "địachỉ": "Địa chỉ",
    "điềukiện": "Điều kiện",
    "điệnthoại": "Điện thoại",
    "địnhnghĩa": "Định nghĩa",
    "đơnvị": "Đơn vị",
    "đơnvịthẩmđịnh": "Đơn vị thẩm định",
    "họcbổng": "Học bổng",
    "họckỳ": "Học kỳ",
    "kháiniệm": "Khái niệm",
    "linktải": "Link tải",
    "ngàybanhành": "Ngày ban hành",
    "nămhọcápdụng": "Năm học áp dụng",
    "ngườiquyếtđịnh": "Người quyết định",
    "nơinộp": "Nơi nộp",
    "nộidung": "Nội dung",
    "quyđịnh": "Quy định",
    "sốhiệu": "Số hiệu",
    "sốtiền": "Số tiền",
    "tênbiểumẫu": "Tên biểu mẫu",
    "thủtục": "Thủ tục",
    "thủtụctiếptheo": "Thủ tục tiếp theo",
    "tómtắt": "Tóm tắt",
    "tốiđa": "Tối đa",
    "tốithiểu": "Tối thiểu",
    "trangweb": "Trang web",
    "trườnghợp": "Trường hợp",
    "vịtrí": "Vị trí",
    "xếploại": "Xếp loại",
    "xemtại": "Xem tại",
    "amount": "Số tiền",
    "email": "Email",
    "level": "Bậc",
    "levelLabel": "Bậc",
    "maximum": "Tối đa",
    "max": "Tối đa",
    "minimum": "Tối thiểu",
    "min": "Tối thiểu",
}


def _label(column: str) -> str:
    return _LABELS.get(column, column)


def render_rows(rows: QueryRows) -> str:
    if not rows:
        return NO_INFORMATION_REPLY

    columns = tuple(rows[0])
    if any(tuple(row) != columns for row in rows):
        raise ValueError("all SPARQL rows must have the same columns")

    # Một cột giữ nguyên cùng một giá trị ở mọi dòng là chú thích cho cả câu
    # trả lời, không phải dữ liệu của từng dòng: nguồn trích dẫn và đường dẫn
    # văn bản lặp lại y hệt trên từng bước của một thủ tục. Tách chúng xuống
    # cuối để danh sách còn đọc được. Quy tắc này thuần hình thức - nó không
    # biết cột nào mang nghĩa gì.
    shared = tuple(
        column for column in columns if len({row[column] for row in rows}) == 1
    )
    listed = tuple(column for column in columns if column not in shared)
    if not listed:
        listed, shared = columns, ()

    if len(listed) == 1:
        values = [_format(row[listed[0]]) for row in rows]
    else:
        values = [
            "\n".join(f"{_label(column)}: {_format(row[column])}" for column in listed)
            for row in rows
        ]

    unique = list(dict.fromkeys(values))
    body = unique[0] if len(unique) == 1 else "\n".join(f"- {value}" for value in unique)

    if shared:
        body += "\n\n" + "\n".join(
            f"{_label(column)}: {_format(rows[0][column])}" for column in shared
        )
    return body


def _format(value: Primitive) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "có" if value else "không"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    # Nhóm hàng nghìn cho số tiền, nhưng chỉ từ 5 chữ số trở lên: năm học và số
    # hiệu điều khoản đều dưới ngưỡng đó nên không bị chấm dấu oan.
    if isinstance(value, int) and abs(value) >= 10000:
        return f"{value:,}".replace(",", ".")
    return str(value)
