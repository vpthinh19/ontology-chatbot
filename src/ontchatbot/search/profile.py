"""Đọc hồ sơ của một node bằng SPARQL, mỗi dữ kiện kèm nguồn basedOn."""

from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import URIRef
from rdflib.namespace import OWL, RDFS
from rdflib.plugins.sparql import prepareQuery

from .entries import EntryKind
from .ontology import Ontology
from .vocabulary import ACADEMIC, compact

_NAMESPACES = {"owl": OWL, "rdfs": RDFS, "academic": ACADEMIC}


@dataclass(frozen=True)
class Source:
    citation: str
    url: str | None = None


@dataclass(frozen=True)
class Fact:
    """Một phát biểu về node hoặc thành phần của nó."""

    kind: EntryKind
    subject: str
    subject_label: str
    property_label: str
    value: str
    target: str | None
    sources: tuple[Source, ...]


@dataclass(frozen=True)
class IncomingRelation:
    """Node khác trỏ tới node đang xem: "<subject_label> <property_label> <node>"."""

    subject: str
    subject_label: str
    property_label: str


@dataclass
class NodeProfile:
    node: str
    label: str
    classes: list[str]
    facts: list[Fact] = field(default_factory=list)
    incoming: list[IncomingRelation] = field(default_factory=list)

    def facts_by_source(self) -> list[tuple[tuple[Source, ...], list[Fact]]]:
        """Gom dữ kiện theo nguồn, giữ thứ tự xuất hiện đầu tiên."""

        groups: dict[tuple[Source, ...], list[Fact]] = {}
        for fact in self.facts:
            groups.setdefault(fact.sources, []).append(fact)
        return list(groups.items())

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "label": self.label,
            "classes": self.classes,
            "facts_by_source": [
                {
                    "sources": [{"citation": source.citation, "url": source.url} for source in sources],
                    "facts": [
                        {"about": fact.subject_label, "property": fact.property_label, "value": fact.value, "target": fact.target}
                        for fact in facts
                    ],
                }
                for sources, facts in self.facts_by_source()
            ],
            "incoming": [
                {"from": relation.subject_label, "property": relation.property_label, "node": relation.subject}
                for relation in self.incoming
            ],
        }


class ProfileReader:
    """Hồ sơ = datatype_property + object_property của node và các thành phần, cộng
    các quan hệ chiều ngược. Nguồn của một dữ kiện là basedOn của chính chủ thể
    khẳng định dữ kiện đó."""

    MAX_COMPONENT_DEPTH = 2

    _DATATYPE_PROPERTIES = prepareQuery(
        """
        SELECT ?property ?property_label ?value WHERE {
          ?node ?property ?value .
          ?property a owl:DatatypeProperty .
          OPTIONAL { ?property rdfs:label ?property_label }
        }
        """,
        initNs=_NAMESPACES,
    )
    _OBJECT_PROPERTIES = prepareQuery(
        """
        SELECT ?property ?property_label ?target ?target_label WHERE {
          ?node ?property ?target .
          ?property a owl:ObjectProperty .
          OPTIONAL { ?property rdfs:label ?property_label }
          OPTIONAL { ?target rdfs:label ?target_label }
        }
        """,
        initNs=_NAMESPACES,
    )
    _INCOMING = prepareQuery(
        """
        SELECT ?subject ?property ?property_label WHERE {
          ?subject ?property ?node .
          ?property a owl:ObjectProperty .
          OPTIONAL { ?property rdfs:label ?property_label }
        }
        """,
        initNs=_NAMESPACES,
    )
    _SOURCES = prepareQuery(
        """
        SELECT ?citation ?document_url ?web_page_url WHERE {
          ?source academic:citationLabel ?citation .
          OPTIONAL { ?source academic:documentUrl ?document_url }
          OPTIONAL { ?source academic:webPageUrl ?web_page_url }
        }
        """,
        initNs=_NAMESPACES,
    )

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology
        self.policy = ontology.policy

    def read(self, node: URIRef) -> NodeProfile:
        return NodeProfile(
            node=compact(node),
            label=self.ontology.label(node),
            classes=self.ontology.class_labels(node),
            facts=self._facts(node, depth=0),
            incoming=self._incoming(node),
        )

    def sources(self, node: URIRef) -> tuple[Source, ...]:
        """Nguồn của node: các phần văn bản trong basedOn; không có thì chính node."""

        based_on = sorted(self.ontology.graph.objects(node, ACADEMIC[self.policy.source_property]), key=str)
        found: list[Source] = []
        for source in based_on or [node]:
            for row in self.ontology.graph.query(self._SOURCES, initBindings={"source": source}):
                url = row.document_url or row.web_page_url
                found.append(Source(str(row.citation), str(url) if url is not None else None))
        return tuple(dict.fromkeys(found))

    def _facts(self, node: URIRef, depth: int) -> list[Fact]:
        subject_label = self.ontology.label(node)
        sources = self.sources(node)
        facts: list[Fact] = []
        for row in self.ontology.graph.query(self._DATATYPE_PROPERTIES, initBindings={"node": node}):
            if self.policy.is_profile_fact(row.property):
                facts.append(
                    Fact(EntryKind.DATATYPE_PROPERTY, compact(node), subject_label, self._property_label(row), str(row.value), None, sources)
                )
        for row in self.ontology.graph.query(self._OBJECT_PROPERTIES, initBindings={"node": node}):
            if self.policy.is_profile_fact(row.property) and not self.policy.is_component(row.property):
                target_label = str(row.target_label) if row.target_label is not None else self.ontology.label(row.target)
                facts.append(
                    Fact(EntryKind.OBJECT_PROPERTY, compact(node), subject_label, self._property_label(row), target_label, compact(row.target), sources)
                )
        facts = sorted(dict.fromkeys(facts), key=lambda fact: (fact.kind.value, fact.property_label, fact.value))
        if depth < self.MAX_COMPONENT_DEPTH:
            for component in self.ontology.components(node):
                facts.extend(self._facts(component, depth + 1))
        return facts

    def _incoming(self, node: URIRef) -> list[IncomingRelation]:
        relations: dict[tuple[str, str], IncomingRelation] = {}
        for row in self.ontology.graph.query(self._INCOMING, initBindings={"node": node}):
            if self.policy.is_component(row.property) or not isinstance(row.subject, URIRef):
                continue
            subject = self.ontology.entry_node(row.subject)
            if subject == node:
                continue
            relation = IncomingRelation(compact(subject), self.ontology.label(subject), self._property_label(row))
            relations.setdefault((relation.subject, relation.property_label), relation)
        return sorted(relations.values(), key=lambda relation: (relation.property_label, relation.subject_label))

    def _property_label(self, row) -> str:
        return str(row.property_label) if row.property_label is not None else self.ontology.label(row.property)
