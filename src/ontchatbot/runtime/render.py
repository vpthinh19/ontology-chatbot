"""Render SPARQL rows as a compact, explicit contract for the LLM agent."""

from __future__ import annotations

import json

from typing import Sequence

from .sparql import QueryRows

_FOUND_GUIDANCE = (
    "Đây là toàn bộ dữ liệu tìm thấy. Đọc hết du_lieu. Nếu chi tiết được hỏi "
    "không xuất hiện, dữ liệu hiện có không chứa chi tiết đó; không tra lại cùng "
    "chủ đề. Mỗi mục trong nguon gồm trích dẫn, đường dẫn, và các dữ kiện mà "
    "nguồn đó khẳng định."
)
_NOT_FOUND_GUIDANCE = (
    "Có thể tra lại một lần với cách gọi ngắn khác; nếu vẫn không có thì dừng."
)

_JSON_KEYS = {
    "thuoctinh": "thuoc_tinh",
    "giatri": "gia_tri",
}
_SOURCE_COLUMNS = ("nguon", "duongdan")


def dump_payload(payload: dict[str, object]) -> str:
    """Serialize the tool contract without spending tokens on JSON whitespace."""

    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


NO_INFORMATION_REPLY = dump_payload(
    {
        "trang_thai": "khong_co_thong_tin",
        "huong_dan": _NOT_FOUND_GUIDANCE,
        "du_lieu": [],
        "nguon": [],
    }
)


def render_rows(rows: QueryRows) -> str:
    """Kết quả của một cụm từ khoá."""

    payload = build_payload(rows)
    return NO_INFORMATION_REPLY if payload is None else dump_payload(payload)


def render_batch(rows: QueryRows, *, missed: Sequence[str] = ()) -> str:
    """Kết quả gộp của nhiều cụm từ khoá gửi cùng một lượt.

    Nêu tên những cụm không tìm thấy gì. Không nêu thì mô hình không phân biệt
    được "chủ đề này không có dữ liệu" với "cụm đó gọi sai tên", và nó sẽ tra
    lại cả loạt.
    """

    payload = build_payload(rows) or json.loads(NO_INFORMATION_REPLY)
    if missed:
        payload["tu_khoa_khong_thay"] = list(missed)
    return dump_payload(payload)


def build_payload(rows: QueryRows) -> dict | None:
    """Trả về JSON: dữ kiện nằm trong chính nguồn đã khẳng định chúng.

    Truy vấn nào cũng chiếu ra cột nguồn và cột đường dẫn trên MỌI dòng, mà một
    trích dẫn dài vài dòng - để nguyên thì trích dẫn lấn hết phần dữ kiện.

    Xếp dữ kiện vào trong nguồn của nó thì trích dẫn chỉ xuất hiện một lần, và
    quan hệ giữa dữ kiện với nguồn nằm ở chính cấu trúc. Không có mã tham chiếu
    nào để mô hình đọc nhầm thành thứ đáng in ra cho người dùng.
    """

    if not rows:
        return None

    columns = tuple(rows[0])
    if any(tuple(row) != columns for row in rows):
        raise ValueError("all SPARQL rows must have the same columns")

    unique_rows = []
    seen_rows = set()
    for row in rows:
        values = tuple(row[column] for column in columns)
        if values not in seen_rows:
            seen_rows.add(values)
            unique_rows.append(row)

    citation_column, link_column = _SOURCE_COLUMNS
    grouped = all(column in columns for column in _SOURCE_COLUMNS)
    if not grouped:
        return {
            "trang_thai": "co_du_lieu",
            "huong_dan": _FOUND_GUIDANCE,
            "du_lieu": [_record(row, columns, ()) for row in unique_rows],
        }

    sources: dict[tuple, dict] = {}
    loose = []
    for row in unique_rows:
        record = _record(row, columns, _SOURCE_COLUMNS)
        pair = (row[citation_column], row[link_column])
        if all(value in (None, "") for value in pair):
            loose.append(record)
            continue
        group = sources.get(pair)
        if group is None:
            group = {"trich_dan": pair[0], "duong_dan": pair[1], "du_lieu": []}
            sources[pair] = group
        group["du_lieu"].append(record)

    payload: dict[str, object] = {
        "trang_thai": "co_du_lieu",
        "huong_dan": _FOUND_GUIDANCE,
        "nguon": list(sources.values()),
    }
    if loose:
        payload["du_lieu_khong_ro_nguon"] = loose
    return payload


def _record(row, columns, skip) -> dict:
    return {
        _JSON_KEYS.get(column, column): row[column]
        for column in columns
        if column not in skip
    }
