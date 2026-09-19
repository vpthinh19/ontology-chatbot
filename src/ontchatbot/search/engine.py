"""Engine: từ khoá → dòng khớp (BM25) → thực thể → hồ sơ gom theo nguồn."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .analyzer import TextAnalyzer
from .builder import IndexBuilder
from .index import EntryHit, SearchIndex
from .ontology import Ontology, TriGFileSource
from .policy import IndexPolicy
from .profile import NodeProfile, ProfileReader


@dataclass
class SearchResult:
    node: str
    label: str
    score: float
    matched: list[EntryHit]
    profile: NodeProfile

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "label": self.label,
            "score": round(self.score, 4),
            "matched": [
                {"kind": hit.entry.kind.value, "text": hit.entry.text, "score": round(hit.score, 4)}
                for hit in self.matched
            ],
            "profile": self.profile.to_dict(),
        }


@dataclass
class SearchResponse:
    keywords: list[str]
    results: list[SearchResult]
    #: Từ khoá không khớp dòng nào.
    unmatched_keywords: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "found" if self.results else "not_found"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "keywords": self.keywords,
            "unmatched_keywords": self.unmatched_keywords,
            "results": [result.to_dict() for result in self.results],
        }


class SearchEngine:
    """Nhận danh sách từ khoá, trả ``top_k`` thực thể kèm hồ sơ, không ngưỡng.

    Điểm của thực thể: với mỗi từ khoá lấy điểm BM25 của dòng khớp tốt nhất của nó, rồi cộng qua
    các từ khoá. Cộng theo từ khoá chứ không theo dòng, nên thực thể nhiều dòng không được cộng dồn.
    """

    def __init__(
        self,
        ontology: Ontology,
        index: SearchIndex,
        reader: ProfileReader | None = None,
        *,
        top_k: int = 5,
        entries_per_keyword: int = 20,
    ) -> None:
        self.ontology = ontology
        self.index = index
        self.reader = reader or ProfileReader(ontology)
        self.top_k = top_k
        self.entries_per_keyword = entries_per_keyword

    @classmethod
    def open(
        cls,
        source: TriGFileSource,
        *,
        policy: IndexPolicy | None = None,
        analyzer: TextAnalyzer | None = None,
        top_k: int = 5,
    ) -> SearchEngine:
        """Nạp ontology và dựng chỉ mục trong bộ nhớ."""

        ontology = Ontology.from_source(source, policy)
        index = SearchIndex(IndexBuilder(ontology).build_entries(), analyzer or TextAnalyzer())
        return cls(ontology, index, top_k=top_k)

    def search(self, keywords: Sequence[str]) -> SearchResponse:
        cleaned = list(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))
        best_rows: dict[str, dict[str, EntryHit]] = {}
        keyword_scores: dict[str, dict[str, float]] = {}
        unmatched: list[str] = []
        for keyword in cleaned:
            hits = self.index.search(keyword, limit=self.entries_per_keyword)
            if not hits:
                unmatched.append(keyword)
            for hit in hits:
                rows = best_rows.setdefault(hit.entry.node, {})
                if hit.entry.text not in rows or hit.score > rows[hit.entry.text].score:
                    rows[hit.entry.text] = hit
                scores = keyword_scores.setdefault(hit.entry.node, {})
                scores[keyword] = max(scores.get(keyword, 0.0), hit.score)

        totals = {node: sum(scores.values()) for node, scores in keyword_scores.items()}
        ranked = sorted(totals, key=lambda node: (-totals[node], node))[: self.top_k]
        results = []
        for node in ranked:
            profile = self.reader.read(node)
            matched = sorted(best_rows[node].values(), key=lambda hit: -hit.score)
            results.append(SearchResult(node, profile.label, totals[node], matched, profile))
        return SearchResponse(cleaned, results, unmatched)
