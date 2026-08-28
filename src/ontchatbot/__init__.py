"""Chatbot học vụ: câu hỏi tiếng Việt chọn ra một truy vấn SPARQL dựng sẵn."""

from importlib import import_module
from typing import Any

__version__ = "3.2.1"

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

_LAZY_EXPORTS = {
    "PREFIXES": (".runtime.sparql", "PREFIXES"),
    "QueryRow": (".runtime.sparql", "QueryRow"),
    "QueryRows": (".runtime.sparql", "QueryRows"),
    "SparqlError": (".runtime.sparql", "SparqlError"),
    "execute_select": (".runtime.sparql", "execute_select"),
    "load_ontology": (".runtime.sparql", "load_ontology"),
    "validate_select": (".research.graph", "validate_select"),
    "OnnxClassifierGenerator": (
        ".runtime.onnx_classifier",
        "OnnxClassifierGenerator",
    ),
    "OntologyChatbot": (".runtime.pipeline", "OntologyChatbot"),
    "render_rows": (".runtime.render", "render_rows"),
}


def __getattr__(name: str) -> Any:
    """Giữ API gói cũ nhưng chỉ nạp tầng native khi thuộc tính được dùng."""

    try:
        module_name, attribute = _LAZY_EXPORTS[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | _LAZY_EXPORTS.keys())
