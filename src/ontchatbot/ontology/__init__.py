"""Ontology layer.

Public API:

* :class:`Ontology` — repository (load + introspect + match + JSON describe)
* :class:`Renderer` — JSON dict → Vietnamese chat string
* :class:`MatchResult` — DTO returned by :meth:`Ontology.resolve`
"""
from .renderer import GREETING_REPLY, OUT_OF_DOMAIN_REPLY, Renderer
from .store import FIXED_KEYS, MatchResult, Ontology

__all__ = [
    "Ontology", "Renderer", "MatchResult",
    "FIXED_KEYS", "GREETING_REPLY", "OUT_OF_DOMAIN_REPLY",
]
