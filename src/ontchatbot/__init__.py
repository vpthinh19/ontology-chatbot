"""NTU academic-procedure chatbot — Vietnamese ontology-grounded NER + RAG."""

__version__ = "0.1.0"


def __getattr__(name):
    """Lazy public exports so importing the package does not load PhoBERT
    or the OWL ontology unless one of the heavy classes is actually used."""
    if name == "Pipeline":
        from .pipeline import Pipeline
        return Pipeline
    if name == "Preprocessor":
        from .preprocessor import Preprocessor
        return Preprocessor
    if name == "NerModel":
        from .ner_model import NerModel
        return NerModel
    if name == "Ontology":
        from .ontology import Ontology
        return Ontology
    if name == "Renderer":
        from .renderer import Renderer
        return Renderer
    raise AttributeError(name)


__all__ = ["Pipeline", "Preprocessor", "NerModel", "Ontology", "Renderer"]
