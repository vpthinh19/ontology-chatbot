"""Engine tìm kiếm trên ontology học vụ.

Dựng (mỗi lần ontology đổi):
    OntologySource ─► Ontology ─► IndexBuilder ─► IndexEntry ─► SearchIndex (BM25)

Tìm (mỗi lượt hỏi):
    từ khoá ─► SearchIndex.search ─► dòng khớp ─► thực thể ─► ProfileReader ─► hồ sơ gom theo nguồn

Ba loại dòng chỉ mục:
    label              "<label>"
    datatype_property  "<label> | <nhãn datatype_property>"
    object_property    "<label> | <nhãn object_property> | <label đích>"
"""

from .analyzer import TextAnalyzer
from .builder import IndexBuilder
from .engine import SearchEngine, SearchResponse, SearchResult
from .entries import EntryKind, IndexEntry
from .index import EntryHit, SearchIndex
from .ontology import Ontology, OntologySource, TriGFileSource
from .profile import Fact, NodeProfile, ProfileReader, Source
from .vocabulary import IndexPolicy, compact, expand, local_name

__all__ = [
    "EntryHit", "EntryKind", "Fact", "IndexBuilder", "IndexEntry", "IndexPolicy", "NodeProfile",
    "Ontology", "OntologySource", "ProfileReader", "SearchEngine", "SearchIndex", "SearchResponse",
    "SearchResult", "Source", "TextAnalyzer", "TriGFileSource", "compact", "expand", "local_name",
]
