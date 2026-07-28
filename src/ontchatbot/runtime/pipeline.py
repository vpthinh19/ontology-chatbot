"""End-to-end question answering over the ontology."""

from __future__ import annotations

from rdflib import Graph

from .gate import DomainGate
from .model import QueryGenerator
from .render import render_rows
from .sparql import execute_select, load_ontology


OUT_OF_SCOPE_REPLY = (
    "Xin lỗi, tôi chỉ có thể trả lời các câu hỏi thuộc phạm vi học vụ hiện có."
)


class OutOfScopeError(ValueError):
    """Raised when the domain gate rejects a question."""


class OntologyChatbot:
    """Connect a query generator to the canonical RDF graph."""

    def __init__(
        self,
        generator: QueryGenerator,
        gate: DomainGate,
        graph: Graph | None = None,
    ) -> None:
        self.generator = generator
        self.gate = gate
        self.graph = graph if graph is not None else load_ontology()

    def answer(self, question: str) -> str:
        if not self.gate.decide(question).accepted:
            raise OutOfScopeError(OUT_OF_SCOPE_REPLY)
        query = self.generator.generate(question)
        return render_rows(execute_select(self.graph, query))
