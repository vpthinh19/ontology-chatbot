"""Render SPARQL rows as a compact, explicit contract for the LLM agent."""

from __future__ import annotations

import json

from .sparql import QueryRows

_FOUND_GUIDANCE = (
    "Đây là toàn bộ dữ liệu tìm thấy. Đọc hết du_lieu. Nếu chi tiết được hỏi "
    "không xuất hiện, dữ liệu hiện có không chứa chi tiết đó; không tra lại cùng "
    "chủ đề."
)
_NOT_FOUND_GUIDANCE = (
    "Có thể tra lại một lần với cách gọi ngắn khác; nếu vẫn không có thì dừng."
)

_JSON_KEYS = {
    "thuoctinh": "thuoc_tinh",
    "giatri": "gia_tri",
}
_SOURCE_COLUMNS = ("nguon", "duongdan")


def _dump(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


NO_INFORMATION_REPLY = _dump(
    {
        "trang_thai": "khong_co_thong_tin",
        "huong_dan": _NOT_FOUND_GUIDANCE,
        "du_lieu": [],
        "nguon": [],
    }
)


def render_rows(rows: QueryRows) -> str:
    """Return valid JSON, preserving rows while factoring repeated sources.

    Catalogue queries conventionally project ``nguon`` and ``duongdan`` on
    every row. Repeating those long strings obscures the actual facts, so each
    distinct pair is emitted once and rows refer to it by ``ma_nguon``.
    """

    if not rows:
        return NO_INFORMATION_REPLY

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

    factor_sources = all(column in columns for column in _SOURCE_COLUMNS)
    source_ids = {}
    sources = []
    data = []

    for row in unique_rows:
        record = {
            _JSON_KEYS.get(column, column): row[column]
            for column in columns
            if not factor_sources or column not in _SOURCE_COLUMNS
        }
        if factor_sources:
            source_pair = (row["nguon"], row["duongdan"])
            if any(value not in (None, "") for value in source_pair):
                source_id = source_ids.get(source_pair)
                if source_id is None:
                    source_id = len(sources) + 1
                    source_ids[source_pair] = source_id
                    sources.append(
                        {
                            "ma_nguon": source_id,
                            "trich_dan": source_pair[0],
                            "duong_dan": source_pair[1],
                        }
                    )
                record["ma_nguon"] = source_id
        data.append(record)

    return _dump(
        {
            "trang_thai": "co_du_lieu",
            "huong_dan": _FOUND_GUIDANCE,
            "du_lieu": data,
            "nguon": sources,
        }
    )
