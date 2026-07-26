"""Minimal CTranslate2 inference pipeline for direct SPARQL generation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from rdflib import Graph

from .model_text import normalize_model_input
from .query_engine import execute_select, load_ontology
from .render import render_rows

MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 160


class QueryGenerator(Protocol):
    def generate(self, text: str) -> str: ...


class CTranslate2Generator:
    """Generate one SPARQL query with a converted local checkpoint."""

    def __init__(self, translator, tokenizer) -> None:
        self._translator = translator
        self._tokenizer = tokenizer

    @classmethod
    def load(
        cls,
        model_dir: Path,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> CTranslate2Generator:
        try:
            import ctranslate2
            from transformers import AutoTokenizer
        except ImportError as exc:  # pragma: no cover - requires inference extra.
            raise RuntimeError("install the inference extra to load a model") from exc

        model_dir = Path(model_dir)
        if not (model_dir / "model.bin").is_file():
            raise FileNotFoundError(f"CTranslate2 model not found: {model_dir}")
        tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
            trust_remote_code=True,
        )
        translator = ctranslate2.Translator(
            str(model_dir),
            device=device,
            compute_type=compute_type,
        )
        return cls(translator, tokenizer)

    def generate(self, text: str) -> str:
        source = normalize_model_input(text)
        if not source:
            raise ValueError("question is empty")
        source_ids = self._tokenizer(
            source,
            add_special_tokens=True,
            max_length=MAX_SOURCE_LENGTH,
            truncation=True,
        ).input_ids
        source_tokens = self._tokenizer.convert_ids_to_tokens(source_ids)
        result = self._translator.translate_batch(
            [source_tokens],
            beam_size=1,
            max_decoding_length=MAX_TARGET_LENGTH,
        )[0]
        target_ids = self._tokenizer.convert_tokens_to_ids(result.hypotheses[0])
        query = self._tokenizer.decode(target_ids, skip_special_tokens=True).strip()
        if not query:
            raise ValueError("model generated an empty query")
        return query


class OntologyChatbot:
    """Connect a query generator to the canonical RDF graph."""

    def __init__(self, generator: QueryGenerator, graph: Graph | None = None) -> None:
        self.generator = generator
        self.graph = graph if graph is not None else load_ontology()

    def answer(self, question: str) -> str:
        query = self.generator.generate(question)
        return render_rows(execute_select(self.graph, query))
