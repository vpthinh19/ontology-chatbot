"""Engine: từ khoá → dòng khớp (BM25) → mục → hồ sơ gom theo nguồn."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .analyzer import TextAnalyzer
from .builder import IndexBuilder
from .index import EntryHit, SearchIndex
from .ontology import Ontology, OntologySource
from .profile import NodeProfile, ProfileReader
from .vocabulary import IndexPolicy


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
    """Công cụ tìm kiếm cho LLM: nhận danh sách từ khoá, trả danh sách thực thể kèm hồ sơ.

    Quy tắc xếp hạng chỉ có một: với mỗi từ khoá, thực thể lấy điểm BM25 của dòng
    khớp tốt nhất của nó; điểm của thực thể là **tổng** các điểm đó. Mô hình viết
    vài từ khoá cho cùng một câu hỏi, nên mục trả lời được nhiều góc của câu hỏi
    đáng đứng trên mục trả lời thật tốt đúng một góc.

    Cộng theo TỪNG TỪ KHOÁ, không cộng theo dòng: một thực thể có nhiều dòng không
    vì thế mà được cộng dồn điểm.
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
        policy: IndexPolicy | None = None,
        analyzer: TextAnalyzer | None = None,
        top_k: int = 3,
    ) -> SearchEngine:
        """Nạp ontology rồi dựng chỉ mục ngay trong bộ nhớ.

        Không có đường nạp chỉ mục đã lưu: dựng lại chỉ tốn vài phần mười giây, còn
        ontology thì sửa bất cứ lúc nào nên tệp chỉ mục hết hạn liên tục.
        """

        ontology = Ontology.from_source(source, policy)
        index = SearchIndex.build(IndexBuilder(ontology).build_entries(),
                                  analyzer or TextAnalyzer(), source.fingerprint())
        return cls(ontology, index, top_k=top_k)

    def search(self, keywords: Sequence[str]) -> SearchResponse:
        cleaned = list(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))
        hits_by_node: dict[str, dict[str, EntryHit]] = {}
        best_per_keyword: dict[str, dict[str, float]] = {}
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
                theo_tu_khoa = best_per_keyword.setdefault(hit.entry.node, {})
                theo_tu_khoa[keyword] = max(theo_tu_khoa.get(keyword, 0.0), hit.score)

        ranked = sorted(
            hits_by_node.items(),
            key=lambda item: (-sum(best_per_keyword[item[0]].values()), item[0]),
        )[: self.top_k]

        results = []
        for node, hits in ranked:
            matched = sorted(hits.values(), key=lambda hit: -hit.score)
            profile = self.reader.read(node)
            results.append(SearchResult(node, profile.label, sum(best_per_keyword[node].values()),
                                        matched, profile))
        return SearchResponse(cleaned, results, unmatched)
