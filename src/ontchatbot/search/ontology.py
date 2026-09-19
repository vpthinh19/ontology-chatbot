"""Đọc đồ thị ontology theo đúng tên gọi của nó.

Đồ thị là tập quad: mỗi câu ba phần nằm trong một túi, tên túi là địa chỉ trích dẫn đã khẳng
định câu đó. Mọi phép đọc ở đây trả về cả túi, nên tầng trên không phải đi tìm nguồn. Câu ngoài
mọi túi là câu không trích dẫn được.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pyoxigraph as oxi

from ..rdf import (
    OUTSIDE,
    RDF_TYPE,
    RDFS_LABEL,
    SKOS_ALT_LABEL,
    compact,
    expand,
    load_trig,
    local_name,
    term,
)
from .policy import IndexPolicy

_IDENTITY = (RDF_TYPE.value, RDFS_LABEL.value, SKOS_ALT_LABEL.value)


class TriGFileSource:
    """Ontology trong một tệp TriG trên đĩa."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> oxi.Store:
        return load_trig(self.path)


@dataclass(frozen=True)
class Assertion:
    """Một câu ba phần kèm túi đã khẳng định nó. ``bag`` là ``None`` khi câu không có nguồn."""

    property: str
    value: str
    target: str | None
    bag: str | None


class Ontology:
    """Đồ thị kèm các phép đọc. Thực thể viết gọn dạng ``:TenCucBo``."""

    def __init__(self, store: oxi.Store, policy: IndexPolicy | None = None) -> None:
        self.store = store
        self.policy = policy or IndexPolicy()

    @classmethod
    def from_source(cls, source: TriGFileSource, policy: IndexPolicy | None = None) -> Ontology:
        return cls(source.load(), policy)

    @staticmethod
    def _node(node: str) -> oxi.NamedNode:
        return oxi.NamedNode(expand(node))

    @staticmethod
    def _bag(graph_name) -> str | None:
        return None if graph_name == OUTSIDE else compact(graph_name.value)

    def _assertion(self, quad: oxi.Quad) -> Assertion:
        if isinstance(quad.object, oxi.NamedNode):
            target = compact(quad.object.value)
            return Assertion(quad.predicate.value, self.label(target), target, self._bag(quad.graph_name))
        return Assertion(quad.predicate.value, quad.object.value, None, self._bag(quad.graph_name))

    # --- danh tính ------------------------------------------------------------

    def individuals(self) -> list[str]:
        """Thực thể tra cứu được: mọi thực thể có lớp, trừ tầng nguồn."""

        typed, sources = set(), set()
        for quad in self.store.quads_for_pattern(None, RDF_TYPE, None, None):
            node = compact(quad.subject.value)
            (sources if self.policy.is_source_class(quad.object.value) else typed).add(node)
        return sorted(typed - sources)

    def individuals_of_class(self, class_name: str) -> list[str]:
        """Thực thể thuộc lớp ``class_name`` (tên cục bộ), xếp theo nhãn."""

        found = {compact(q.subject.value) for q in self.store.quads_for_pattern(None, RDF_TYPE, term(class_name), None)}
        return sorted(found, key=self.label)

    def label(self, node: str) -> str:
        """Nhãn hiển thị. IRI ngoài namespace học vụ (đường dẫn chẳng hạn) không có nhãn: chính nó là giá trị."""

        for quad in self.store.quads_for_pattern(self._node(node), RDFS_LABEL, None, None):
            return quad.object.value
        return local_name(node) if node.startswith(":") else node

    def labels(self, node: str) -> list[str]:
        """Mọi tên gọi: nhãn chính trước, tên gọi khác sau."""

        iri = self._node(node)
        main = sorted(q.object.value for q in self.store.quads_for_pattern(iri, RDFS_LABEL, None, None))
        alt = sorted(q.object.value for q in self.store.quads_for_pattern(iri, SKOS_ALT_LABEL, None, None))
        return list(dict.fromkeys(main + alt))

    def class_labels(self, node: str) -> list[str]:
        """Nhãn của lớp, cộng nhãn của ô "loại" (``loaiQuyTac``...) nếu có."""

        iri = self._node(node)
        found = [self.label(compact(q.object.value)) for q in self.store.quads_for_pattern(iri, RDF_TYPE, None, None)]
        for quad in self.store.quads_for_pattern(iri, None, None, None):
            if local_name(quad.predicate.value).startswith(self.policy.type_property_prefix):
                found.append(self.label(compact(quad.object.value)))
        return sorted(dict.fromkeys(found))

    def property_label(self, property_iri: str) -> str:
        return self.label(compact(property_iri))

    # --- câu khẳng định -------------------------------------------------------

    def assertions(self, node: str) -> Iterator[Assertion]:
        """Câu có ``node`` làm chủ ngữ, trừ câu danh tính và câu dựng trích dẫn."""

        quads = self.store.quads_for_pattern(self._node(node), None, None, None)
        for quad in sorted(quads, key=lambda q: (q.predicate.value, str(q.object))):
            prop = quad.predicate.value
            if prop not in _IDENTITY and self.policy.is_profile_fact(prop):
                yield self._assertion(quad)

    def assertions_raw(self, node: str) -> Iterator[Assertion]:
        """Mọi câu có ``node`` làm chủ ngữ, không lọc; dùng để đọc tầng nguồn."""

        for quad in self.store.quads_for_pattern(self._node(node), None, None, None):
            yield self._assertion(quad)

    def incoming(self, node: str) -> Iterator[tuple[str, Assertion]]:
        """Câu có ``node`` làm đích, dạng (chủ ngữ viết gọn, câu)."""

        quads = self.store.quads_for_pattern(None, None, self._node(node), None)
        for quad in sorted(quads, key=lambda q: (q.predicate.value, q.subject.value)):
            prop = quad.predicate.value
            if prop != RDF_TYPE.value and self.policy.is_profile_fact(prop):
                yield compact(quad.subject.value), Assertion(prop, self.label(node), compact(node),
                                                             self._bag(quad.graph_name))
