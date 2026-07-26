"""End-to-end question answering over the ontology."""

from __future__ import annotations

from rdflib import Graph

from .model import QueryGenerator
from .render import render_rows
from .sparql import execute_select, load_ontology


class OntologyChatbot:
    """Connect a query generator to the canonical RDF graph."""

    def __init__(self, generator: QueryGenerator, graph: Graph | None = None) -> None:
        self.generator = generator
        self.graph = graph if graph is not None else load_ontology()

    def answer(self, question: str) -> str:
        query = self.generator.generate(question)
        return render_rows(execute_select(self.graph, query))
