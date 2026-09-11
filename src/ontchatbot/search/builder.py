"""Quét ontology để sinh các dòng chỉ mục."""

from __future__ import annotations

from rdflib import URIRef

from .entries import EntryKind, IndexEntry
from .ontology import Ontology
from .vocabulary import compact


class IndexBuilder:
    """Sinh ba loại dòng cho mỗi individual:

    - ``label``:             "<label>" cho rdfs:label và mỗi skos:altLabel
    - ``datatype_property``: "<label> | <nhãn datatype_property>", mỗi thuộc tính một dòng
    - ``object_property``:   "<label> | <nhãn object_property> | <label của đích>"

    Mọi dòng trỏ về node gốc của individual, nên tìm trúng một bước thì kết quả vẫn
    là thủ tục chứa bước đó.
    """

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology

    def build_entries(self) -> list[IndexEntry]:
        entries: dict[tuple, IndexEntry] = {}
        for individual in self.ontology.individuals():
            node = self.ontology.entry_node(individual)
            for entry in (
                *self._label_entries(individual, node),
                *self._datatype_property_entries(individual, node),
                *self._object_property_entries(individual, node),
            ):
                entries.setdefault((entry.kind, entry.text, entry.node, entry.property, entry.target), entry)
        return list(entries.values())

    def _label_entries(self, individual: URIRef, node: URIRef) -> list[IndexEntry]:
        return [
            IndexEntry(EntryKind.LABEL, text, compact(node), compact(individual))
            for text in self.ontology.labels(individual)
        ]

    def _datatype_property_entries(self, individual: URIRef, node: URIRef) -> list[IndexEntry]:
        subject = self.ontology.label(individual)
        properties = dict.fromkeys(
            prop
            for prop, _value in self.ontology.datatype_property_assertions(individual)
            if self.ontology.policy.is_indexed(prop)
        )
        return [
            IndexEntry(
                EntryKind.DATATYPE_PROPERTY,
                f"{subject} | {self.ontology.label(prop)}",
                compact(node),
                compact(individual),
                property=compact(prop),
            )
            for prop in properties
        ]

    def _object_property_entries(self, individual: URIRef, node: URIRef) -> list[IndexEntry]:
        subject = self.ontology.label(individual)
        return [
            IndexEntry(
                EntryKind.OBJECT_PROPERTY,
                f"{subject} | {self.ontology.label(prop)} | {self.ontology.label(target)}",
                compact(node),
                compact(individual),
                property=compact(prop),
                target=compact(target),
            )
            for prop, target in self.ontology.object_property_assertions(individual)
            if self.ontology.policy.is_indexed(prop)
        ]
