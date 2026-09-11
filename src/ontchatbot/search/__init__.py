"""Engine tìm kiếm trên ontology học vụ.

Dựng (mỗi lần ontology đổi):
    OntologySource ─► Ontology ─► IndexBuilder ─► IndexEntry ─► SearchIndex (BM25)

Tìm (mỗi lượt hỏi):
    từ khoá ─► SearchIndex.search ─► dòng khớp ─► node ─► ProfileReader (SPARQL) ─► hồ sơ kèm nguồn

Ba loại dòng chỉ mục:
    label              "<label>"
    datatype_property  "<label> | <nhãn datatype_property>"
    object_property    "<label> | <nhãn object_property> | <label đích>"
"""

from .analyzer import TextAnalyzer
from .builder import IndexBuilder
from .engine import SearchEngine, SearchResponse, SearchResult, StaleIndexError
from .entries import EntryKind, IndexEntry
from .index import EntryHit, SearchIndex
from .ontology import Ontology, OntologySource, TurtleFileSource
from .profile import Fact, IncomingRelation, NodeProfile, ProfileReader, Source
from .vocabulary import ACADEMIC, IndexPolicy

__all__ = [
    "ACADEMIC", "EntryHit", "EntryKind", "Fact", "IncomingRelation", "IndexBuilder", "IndexEntry",
    "IndexPolicy", "NodeProfile", "Ontology", "OntologySource", "ProfileReader", "SearchEngine",
    "SearchIndex", "SearchResponse", "SearchResult", "Source", "StaleIndexError", "TextAnalyzer",
    "TurtleFileSource",
]
