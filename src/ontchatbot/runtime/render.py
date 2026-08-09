"""Generic rendering for SPARQL rows; no ontology-specific result DTOs."""

from __future__ import annotations

from .sparql import Primitive, QueryRows

NO_INFORMATION_REPLY = "Không có thông tin."


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
            "\n".join(f"{column}: {_format(row[column])}" for column in listed)
            for row in rows
        ]

    unique = list(dict.fromkeys(values))
    body = unique[0] if len(unique) == 1 else "\n".join(f"- {value}" for value in unique)

    if shared:
        body += "\n\n" + "\n".join(
            f"{column}: {_format(rows[0][column])}" for column in shared
        )
    return body


def _format(value: Primitive) -> str:
    return "—" if value is None else str(value)
