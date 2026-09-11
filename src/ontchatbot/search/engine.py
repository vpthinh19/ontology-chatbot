"""Engine: từ khoá → dòng khớp (BM25) → node → hồ sơ đọc bằng SPARQL."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .analyzer import TextAnalyzer
from .builder import IndexBuilder
from .index import EntryHit, SearchIndex
from .ontology import Ontology, OntologySource
from .profile import NodeProfile, ProfileReader
from .vocabulary import IndexPolicy, expand


class StaleIndexError(RuntimeError):
    """Chỉ mục đã lưu được dựng từ một phiên bản ontology khác."""


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
    #: Từ khoá không khớp dòng nào trong chỉ mục.
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
    """Công cụ tìm kiếm cho LLM: nhận danh sách từ khoá, trả danh sách node kèm hồ sơ.

    Quy tắc xếp hạng node chỉ có một: điểm của node là điểm BM25 cao nhất trong các
    dòng trỏ về nó, xét trên mọi từ khoá. Lấy ``top_k`` node đầu.
    """

    def __init__(
        self,
        ontology: Ontology,
        index: SearchIndex,
        reader: ProfileReader | None = None,
        *,
        top_k: int = 3,
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
        source: OntologySource,
        *,
        index_directory: Path | None = None,
        policy: IndexPolicy | None = None,
        analyzer: TextAnalyzer | None = None,
        top_k: int = 3,
    ) -> SearchEngine:
        """Nạp ontology; dùng chỉ mục đã lưu nếu có, không thì dựng ngay trong bộ nhớ."""

        analyzer = analyzer or TextAnalyzer()
        ontology = Ontology.from_source(source, policy)
        fingerprint = source.fingerprint()
        if index_directory is None:
            index = SearchIndex.build(IndexBuilder(ontology).build_entries(), analyzer, fingerprint)
        else:
            index = SearchIndex.load(index_directory, analyzer)
            if index.fingerprint != fingerprint:
                raise StaleIndexError(f"chỉ mục tại {index_directory} không khớp phiên bản ontology; hãy build lại")
            if index.analyzer_name != analyzer.name:
                raise StaleIndexError(
                    f"chỉ mục tại {index_directory} dựng bằng cách tách từ {index.analyzer_name}, "
                    f"khác {analyzer.name}; hãy build lại"
                )
        return cls(ontology, index, top_k=top_k)

    def search(self, keywords: Sequence[str]) -> SearchResponse:
        cleaned = list(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))
        hits_by_node: dict[str, dict[str, EntryHit]] = {}
        unmatched: list[str] = []
        for keyword in cleaned:
            hits = self.index.search(keyword, limit=self.entries_per_keyword)
            if not hits:
                unmatched.append(keyword)
            for hit in hits:
                best = hits_by_node.setdefault(hit.entry.node, {})
                previous = best.get(hit.entry.text)
                if previous is None or hit.score > previous.score:
                    best[hit.entry.text] = hit

        ranked = sorted(
            hits_by_node.items(),
            key=lambda item: (-max(hit.score for hit in item[1].values()), item[0]),
        )[: self.top_k]

        results = []
        for node, hits in ranked:
            matched = sorted(hits.values(), key=lambda hit: -hit.score)
            profile = self.reader.read(expand(node))
            results.append(SearchResult(node, profile.label, matched[0].score, matched, profile))
        return SearchResponse(cleaned, results, unmatched)
