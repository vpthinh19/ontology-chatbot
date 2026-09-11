"""Chỉ mục BM25 trên các dòng. Lớp này không biết gì về đồ thị."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import bm25s

from .analyzer import TextAnalyzer
from .entries import IndexEntry


@dataclass(frozen=True)
class EntryHit:
    entry: IndexEntry
    score: float


class SearchIndex:
    """Tìm các dòng chứa từ của từ khoá, xếp hạng bằng BM25."""

    ENTRIES_FILE = "entries.jsonl"
    BM25_DIRECTORY = "bm25"
    MANIFEST_FILE = "manifest.json"

    def __init__(self, entries: list[IndexEntry], retriever: bm25s.BM25, analyzer: TextAnalyzer, fingerprint: str) -> None:
        self.entries = entries
        self.retriever = retriever
        self.analyzer = analyzer
        self.fingerprint = fingerprint

    @classmethod
    def build(cls, entries: list[IndexEntry], analyzer: TextAnalyzer, fingerprint: str) -> SearchIndex:
        retriever = bm25s.BM25()
        retriever.index([analyzer.terms(entry.text) for entry in entries], show_progress=False)
        return cls(entries, retriever, analyzer, fingerprint)

    def search(self, keyword: str, limit: int = 20) -> list[EntryHit]:
        """Các dòng có chung ít nhất một từ với từ khoá, điểm cao trước."""

        tokens = self.analyzer.terms(keyword)
        if not tokens or not self.entries:
            return []
        rows, scores = self.retriever.retrieve([tokens], k=min(limit, len(self.entries)), show_progress=False)
        return [
            EntryHit(self.entries[int(row)], float(score))
            for row, score in zip(rows[0], scores[0])
            if score > 0
        ]

    # --- lưu và nạp -----------------------------------------------------------

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / self.ENTRIES_FILE, "w", encoding="utf-8") as handle:
            for entry in self.entries:
                handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        self.retriever.save(directory / self.BM25_DIRECTORY, show_progress=False)
        manifest = {
            "fingerprint": self.fingerprint,
            "entries": len(self.entries),
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (directory / self.MANIFEST_FILE).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, directory: Path, analyzer: TextAnalyzer) -> SearchIndex:
        directory = Path(directory)
        manifest = json.loads((directory / cls.MANIFEST_FILE).read_text(encoding="utf-8"))
        with open(directory / cls.ENTRIES_FILE, encoding="utf-8") as handle:
            entries = [IndexEntry.from_dict(json.loads(line)) for line in handle if line.strip()]
        retriever = bm25s.BM25.load(directory / cls.BM25_DIRECTORY, show_progress=False)
        return cls(entries, retriever, analyzer, manifest["fingerprint"])
