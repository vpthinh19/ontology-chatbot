"""Nơi lấy ontology và cách đọc đồ thị theo đúng tên gọi của nó."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from .vocabulary import ACADEMIC, IndexPolicy, local_name


class OntologySource(ABC):
    """Nơi cất ontology. Bản nháp đọc tệp; bản triển khai sẽ đọc GCS."""

    @abstractmethod
    def load(self) -> Graph:
        """Nạp toàn bộ ontology vào bộ nhớ."""

    @abstractmethod
    def fingerprint(self) -> str:
        """Định danh phiên bản, dùng để biết chỉ mục đã lưu còn khớp không."""


class TurtleFileSource(OntologySource):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self) -> Graph:
        graph = Graph()
        graph.parse(self.path, format="turtle")
        return graph

    def fingerprint(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


class Ontology:
    """Đồ thị kèm các phép đọc: individual, label, object_property, datatype_property."""

    def __init__(self, graph: Graph, policy: IndexPolicy | None = None) -> None:
        self.graph = graph
        self.policy = policy or IndexPolicy()
        self.object_properties = frozenset(graph.subjects(RDF.type, OWL.ObjectProperty))
        self.datatype_properties = frozenset(graph.subjects(RDF.type, OWL.DatatypeProperty))
        self._parent = self._component_parents()

    @classmethod
    def from_source(cls, source: OntologySource, policy: IndexPolicy | None = None) -> Ontology:
        return cls(source.load(), policy)

    # --- individual và label -------------------------------------------------

    def individuals(self) -> list[URIRef]:
        return sorted(
            {node for node in self.graph.subjects(RDF.type, OWL.NamedIndividual) if isinstance(node, URIRef)},
            key=str,
        )

    def label(self, node: URIRef) -> str:
        """Tên hiển thị: rdfs:label đầu tiên, không có thì dùng tên cục bộ của IRI."""

        labels = sorted(str(value) for value in self.graph.objects(node, RDFS.label))
        return labels[0] if labels else local_name(node)

    def labels(self, node: URIRef) -> list[str]:
        """Mọi tên gọi: rdfs:label trước, skos:altLabel sau."""

        main = sorted(str(value) for value in self.graph.objects(node, RDFS.label))
        alternative = sorted(str(value) for value in self.graph.objects(node, SKOS.altLabel))
        return list(dict.fromkeys(main + alternative))

    def individuals_of_class(self, class_name: str) -> list[URIRef]:
        """Individual mang đúng lớp ``class_name`` (tên cục bộ), xếp theo label."""

        members = {node for node in self.graph.subjects(RDF.type, ACADEMIC[class_name]) if isinstance(node, URIRef)}
        return sorted(members, key=self.label)

    def class_labels(self, node: URIRef) -> list[str]:
        classes = (cls for cls in self.graph.objects(node, RDF.type) if cls != OWL.NamedIndividual)
        return sorted(self.label(cls) for cls in classes if isinstance(cls, URIRef))

    # --- object_property và datatype_property -------------------------------

    def is_object_property(self, prop: URIRef) -> bool:
        return prop in self.object_properties

    def is_datatype_property(self, prop: URIRef) -> bool:
        return prop in self.datatype_properties

    def object_property_assertions(self, node: URIRef) -> Iterator[tuple[URIRef, URIRef]]:
        """Các cặp (object_property, individual đích) mà node là chủ thể."""

        for prop, target in sorted(self.graph.predicate_objects(node), key=lambda pair: (str(pair[0]), str(pair[1]))):
            if self.is_object_property(prop) and isinstance(target, URIRef):
                yield prop, target

    def datatype_property_assertions(self, node: URIRef) -> Iterator[tuple[URIRef, Literal]]:
        """Các cặp (datatype_property, giá trị) mà node là chủ thể."""

        for prop, value in sorted(self.graph.predicate_objects(node), key=lambda pair: (str(pair[0]), str(pair[1]))):
            if self.is_datatype_property(prop) and isinstance(value, Literal):
                yield prop, value

    # --- thành phần và node gốc ---------------------------------------------

    def entry_node(self, node: URIRef) -> URIRef:
        """Node mà câu trả lời xoay quanh: bước và điều kiện quy về thủ tục chứa nó."""

        seen = {node}
        while node in self._parent and self._parent[node] not in seen:
            node = self._parent[node]
            seen.add(node)
        return node

    def components(self, node: URIRef) -> list[URIRef]:
        """Thành phần trực tiếp của node, sắp theo thuộc tính thứ tự rồi theo label."""

        children = {
            target
            for prop, target in self.object_property_assertions(node)
            if self.policy.is_component(prop)
        }
        return sorted(children, key=lambda child: (self._order_of(child), self.label(child)))

    def _order_of(self, node: URIRef) -> int:
        for name in self.policy.order_properties:
            value = self.graph.value(node, ACADEMIC[name])
            if value is not None:
                try:
                    return int(value)
                except ValueError:
                    break
        return 1_000_000

    def _component_parents(self) -> dict[URIRef, URIRef]:
        parent: dict[URIRef, URIRef] = {}
        for name in sorted(self.policy.component_properties):
            for subject, target in sorted(self.graph.subject_objects(ACADEMIC[name]), key=lambda pair: (str(pair[0]), str(pair[1]))):
                if isinstance(subject, URIRef) and isinstance(target, URIRef):
                    parent.setdefault(target, subject)
        return parent
