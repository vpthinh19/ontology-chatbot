"""Cross-cutting infrastructure: configuration, logging, and the
orchestration pipeline that glues together the NER, ontology and rendering
subsystems.

Public API:

* :class:`Pipeline` (lazily exposed) — ``Pipeline.get().answer(query)``
"""

from __future__ import annotations


def __getattr__(name):  # PEP 562 — module-level lazy attribute access
    """Expose :class:`Pipeline` lazily so importing this package does not
    eagerly load the ontology + NER head. The lazy form also breaks an
    import cycle that would otherwise occur if :mod:`ontology` is imported
    before :mod:`core`.
    """
    if name == "Pipeline":
        from .pipeline import Pipeline as _Pipeline
        return _Pipeline
    raise AttributeError(name)


__all__ = ["Pipeline"]
