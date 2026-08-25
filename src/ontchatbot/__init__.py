"""Chatbot học vụ: câu hỏi tiếng Việt chọn ra một truy vấn SPARQL dựng sẵn."""

from .runtime.sparql import (
    PREFIXES,
    QueryRow,
    QueryRows,
    SparqlError,
    execute_select,
    load_ontology,
    validate_select,
)
from .runtime.onnx_classifier import OnnxClassifierGenerator
from .runtime.pipeline import OntologyChatbot
from .runtime.render import render_rows

__version__ = "3.0.2"

__all__ = [
    "PREFIXES",
    "OnnxClassifierGenerator",
    "OntologyChatbot",
    "QueryRow",
    "QueryRows",
    "SparqlError",
    "execute_select",
    "load_ontology",
    "render_rows",
    "validate_select",
]
