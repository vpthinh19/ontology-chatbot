"""Chỉ mục BM25 trên các dòng. Lớp này không biết gì về đồ thị."""

from __future__ import annotations

from dataclasses import dataclass

import bm25s

from .analyzer import TextAnalyzer
from .entries import IndexEntry


@dataclass(frozen=True)
class EntryHit:
    entry: IndexEntry
    score: float


class SearchIndex:
    """Tìm các dòng có chung từ với từ khoá, xếp hạng bằng BM25 (k1 = 1,5, b = 0,75)."""

    def __init__(self, entries: list[IndexEntry], analyzer: TextAnalyzer) -> None:
        self.entries = entries
        self.analyzer = analyzer
        self._retriever = bm25s.BM25()
        self._retriever.index([analyzer.terms(entry.text) for entry in entries], show_progress=False)

    def search(self, keyword: str, limit: int = 20) -> list[EntryHit]:
        """Các dòng có chung ít nhất một từ với từ khoá, điểm cao trước."""

        tokens = self.analyzer.terms(keyword)
        if not tokens or not self.entries:
            return []
        rows, scores = self._retriever.retrieve([tokens], k=min(limit, len(self.entries)), show_progress=False)
        return [EntryHit(self.entries[int(row)], float(score)) for row, score in zip(rows[0], scores[0]) if score > 0]
