"""NTU ontology chatbot: Vietnamese text to direct SPARQL."""

from .runtime.sparql import (
    PREFIXES,
    QueryRow,
    QueryRows,
    SparqlError,
    execute_select,
    load_ontology,
    validate_select,
)
from .runtime.model import CTranslate2Generator
from .runtime.pipeline import OntologyChatbot
from .runtime.render import render_rows

__version__ = "0.4.1"

__all__ = [
    "PREFIXES",
    "CTranslate2Generator",
    "OntologyChatbot",
    "QueryRow",
    "QueryRows",
    "SparqlError",
    "execute_select",
    "load_ontology",
    "render_rows",
    "validate_select",
]
