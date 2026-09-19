"""Engine tìm kiếm trên ontology học vụ.

Dựng (mỗi lần ontology đổi):
    TriGFileSource ─► Ontology ─► IndexBuilder ─► IndexEntry ─► SearchIndex (BM25)

Tìm (mỗi lượt tra cứu):
    từ khoá ─► SearchIndex.search ─► dòng khớp ─► thực thể ─► ProfileReader ─► hồ sơ gom theo nguồn
"""

from .analyzer import TextAnalyzer
from .builder import IndexBuilder
from .engine import SearchEngine, SearchResponse, SearchResult
from .entries import EntryKind, IndexEntry
from .index import EntryHit, SearchIndex
from .ontology import Assertion, Ontology, TriGFileSource
from .policy import IndexPolicy
from .profile import Fact, NodeProfile, ProfileReader, Source

__all__ = [
    "Assertion", "EntryHit", "EntryKind", "Fact", "IndexBuilder", "IndexEntry", "IndexPolicy", "NodeProfile",
    "Ontology", "ProfileReader", "SearchEngine", "SearchIndex", "SearchResponse", "SearchResult", "Source",
    "TextAnalyzer", "TriGFileSource",
]
