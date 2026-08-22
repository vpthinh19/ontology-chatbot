"""Giao diện chung cho bộ chọn truy vấn SPARQL."""

from __future__ import annotations

from typing import Protocol, Sequence


class QueryGenerator(Protocol):
    def generate(self, text: str) -> str: ...

    def generate_many(self, texts: Sequence[str]) -> list[str]: ...


class QueryGenerationError(ValueError):
    """Bộ chọn không thể trả về một truy vấn dùng được."""
