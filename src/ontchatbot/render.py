"""Generic rendering for SPARQL rows; no ontology-specific result DTOs."""

from __future__ import annotations

from .query_engine import Primitive, QueryRows


def render_rows(rows: QueryRows) -> str:
    if not rows:
        return "Không tìm thấy thông tin phù hợp."

    columns = tuple(rows[0])
    if any(tuple(row) != columns for row in rows):
        raise ValueError("all SPARQL rows must have the same columns")

    if len(columns) == 1:
        values = [_format(row[columns[0]]) for row in rows]
        return values[0] if len(values) == 1 else "\n".join(f"- {value}" for value in values)

    rendered = [
        "; ".join(f"{column}: {_format(row[column])}" for column in columns)
        for row in rows
    ]
    return rendered[0] if len(rendered) == 1 else "\n".join(f"- {row}" for row in rendered)


def _format(value: Primitive) -> str:
    return "—" if value is None else str(value)
