"""Cross-cutting infrastructure: configuration, logging, and the orchestration
pipeline that glues together the NER, ontology and rendering subsystems."""

from .pipeline import answer

__all__ = ["answer"]
