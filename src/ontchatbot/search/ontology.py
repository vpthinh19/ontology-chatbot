"""Nơi lấy ontology và cách đọc đồ thị theo đúng tên gọi của nó.

Đồ thị là một tập quad: mỗi câu ba phần nằm trong một cái túi, và tên túi là địa
chỉ trích dẫn đã khẳng định câu đó. Nhờ vậy mọi phép đọc ở đây trả về kèm cái túi,
và tầng trên không phải đi tìm nguồn ở đâu nữa.

Câu nằm ngoài mọi túi là câu không có nguồn: danh tính do ta đặt, và những điều ta
khẳng định bằng thẩm quyền của mình. Chúng nói ra được nhưng không trích dẫn được.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pyoxigraph as oxi

from ..settings import ONTOLOGY_NS
from .vocabulary import IndexPolicy, compact, expand, local_name

RDF_TYPE = oxi.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_LABEL = oxi.NamedNode("http://www.w3.org/2000/01/rdf-schema#label")
SKOS_ALT_LABEL = oxi.NamedNode("http://www.w3.org/2004/02/skos/core#altLabel")
NGOAI_TUI = oxi.DefaultGraph()


class OntologySource(ABC):
    """Nơi cất ontology. Bản nháp đọc tệp; bản triển khai sẽ đọc GCS."""

    @abstractmethod
    def load(self) -> oxi.Store:
        """Nạp toàn bộ ontology vào bộ nhớ."""

    @abstractmethod
    def fingerprint(self) -> str:
        """Định danh phiên bản, dùng để biết chỉ mục đã lưu còn khớp không."""


class TriGFileSource(OntologySource):
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> oxi.Store:
        store = oxi.Store()
        store.load(path=str(self.path), format=oxi.RdfFormat.TRIG)
        return store

    def fingerprint(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class Assertion:
    """Một câu ba phần kèm cái túi đã khẳng định nó. ``bag`` rỗng là không có nguồn."""

    property: str
    value: str
    target: str | None
    bag: str | None


class Ontology:
    """Đồ thị kèm các phép đọc. Mỗi phép đọc trả về cả cái túi của câu."""

    def __init__(self, store: oxi.Store, policy: IndexPolicy | None = None) -> None:
        self.store = store
        self.policy = policy or IndexPolicy()

    @classmethod
    def from_source(cls, source: OntologySource, policy: IndexPolicy | None = None) -> Ontology:
        return cls(source.load(), policy)

    # --- tiện ích -----------------------------------------------------------

    @staticmethod
    def _node(iri: str) -> oxi.NamedNode:
        return oxi.NamedNode(str(expand(iri)))

    @staticmethod
    def _ten_tui(graph_name) -> str | None:
        return None if graph_name == NGOAI_TUI else compact(graph_name.value)

    def _mot(self, node: oxi.NamedNode, prop: oxi.NamedNode) -> str | None:
        for quad in self.store.quads_for_pattern(node, prop, None, None):
            return quad.object.value
        return None

    # --- danh tính ----------------------------------------------------------

    def individuals(self) -> list[str]:
        """Thực thể tra cứu được. Tầng nguồn không nằm trong đây: nó là bộ máy
        trích dẫn, không phải thứ người ta hỏi tới."""

        ra = set()
        for quad in self.store.quads_for_pattern(None, RDF_TYPE, None, None):
            if local_name(quad.object.value) in self.policy.source_classes:
                ra.discard(compact(quad.subject.value))
                continue
            ra.add(compact(quad.subject.value))
        bo_qua = {compact(q.subject.value) for q in self.store.quads_for_pattern(None, RDF_TYPE, None, None)
                  if local_name(q.object.value) in self.policy.source_classes}
        return sorted(ra - bo_qua)

    def individuals_of_class(self, class_name: str) -> list[str]:
        """Thực thể mang đúng lớp ``class_name`` (tên cục bộ), xếp theo nhãn."""

        lop = oxi.NamedNode(ONTOLOGY_NS + class_name)
        ra = {compact(q.subject.value) for q in self.store.quads_for_pattern(None, RDF_TYPE, lop, None)}
        return sorted(ra, key=self.label)

    def label(self, node: str) -> str:
        """Nhãn hiển thị. IRI ngoài namespace học vụ - đường dẫn chẳng hạn - không có
        nhãn và cũng không nên bị cắt thành tên cục bộ: chính nó là giá trị."""

        nhan = self._mot(self._node(node), RDFS_LABEL)
        if nhan is not None:
            return nhan
        return local_name(node) if node.startswith(":") else node

    def labels(self, node: str) -> list[str]:
        """Mọi tên gọi: nhãn chính trước, tên gọi phụ sau."""

        iri = self._node(node)
        chinh = sorted(q.object.value for q in self.store.quads_for_pattern(iri, RDFS_LABEL, None, None))
        phu = sorted(q.object.value for q in self.store.quads_for_pattern(iri, SKOS_ALT_LABEL, None, None))
        return list(dict.fromkeys(chinh + phu))

    def class_labels(self, node: str) -> list[str]:
        """Nhãn của lớp, cộng nhãn của ô "loại" nếu có - đó mới là thứ nói rõ
        đây là quy tắc gì, chứng chỉ loại nào."""

        iri = self._node(node)
        ra = [self.label(compact(q.object.value))
              for q in self.store.quads_for_pattern(iri, RDF_TYPE, None, None)]
        for quad in self.store.quads_for_pattern(iri, None, None, None):
            if local_name(quad.predicate.value).startswith(self.policy.type_property_prefix):
                ra.append(self.label(compact(quad.object.value)))
        return sorted(dict.fromkeys(ra))

    # --- câu khẳng định ------------------------------------------------------

    def assertions(self, node: str) -> Iterator[Assertion]:
        """Mọi câu mà node này là chủ ngữ, trừ câu danh tính."""

        for quad in sorted(self.store.quads_for_pattern(self._node(node), None, None, None),
                           key=lambda q: (q.predicate.value, str(q.object))):
            prop = quad.predicate.value
            if prop in (RDF_TYPE.value, RDFS_LABEL.value, SKOS_ALT_LABEL.value):
                continue
            if not self.policy.is_profile_fact(prop):
                continue
            if isinstance(quad.object, oxi.NamedNode):
                yield Assertion(prop, self.label(compact(quad.object.value)),
                                compact(quad.object.value), self._ten_tui(quad.graph_name))
            else:
                yield Assertion(prop, quad.object.value, None, self._ten_tui(quad.graph_name))

    def assertions_raw(self, node: str) -> Iterator[Assertion]:
        """Như ``assertions`` nhưng không lọc gì - dùng để đọc tầng nguồn."""

        for quad in self.store.quads_for_pattern(self._node(node), None, None, None):
            if isinstance(quad.object, oxi.NamedNode):
                yield Assertion(quad.predicate.value, self.label(compact(quad.object.value)),
                                compact(quad.object.value), self._ten_tui(quad.graph_name))
            else:
                yield Assertion(quad.predicate.value, quad.object.value, None,
                                self._ten_tui(quad.graph_name))

    def incoming(self, node: str) -> Iterator[tuple[str, Assertion]]:
        """Câu mà node này là đích. Trả về (chủ ngữ viết gọn, câu)."""

        for quad in sorted(self.store.quads_for_pattern(None, None, self._node(node), None),
                           key=lambda q: (q.predicate.value, q.subject.value)):
            prop = quad.predicate.value
            if not self.policy.is_profile_fact(prop) or prop == RDF_TYPE.value:
                continue
            chu_the = compact(quad.subject.value)
            yield chu_the, Assertion(prop, self.label(node), compact(node), self._ten_tui(quad.graph_name))

    def property_label(self, property_iri: str) -> str:
        return self.label(compact(property_iri))
