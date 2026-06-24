"""NTU academic-procedure chatbot - model sinh cây truy vấn JSON + duyệt ontology."""

__version__ = "0.1.0"


def __getattr__(name):
    """Export lười: import gói không kéo theo owlready2/BARTpho trừ khi thực sự dùng."""
    if name == "Pipeline":
        from .pipeline import Pipeline
        return Pipeline
    if name == "Ontology":
        from .ontology import Ontology
        return Ontology
    if name == "TreeModel":
        from .model import TreeModel
        return TreeModel
    raise AttributeError(name)


__all__ = ["Pipeline", "Ontology", "TreeModel"]
