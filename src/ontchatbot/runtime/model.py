"""Minimal CTranslate2 inference pipeline for direct SPARQL generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .text import normalize_model_input

MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 160


class QueryGenerator(Protocol):
    def generate(self, text: str) -> str: ...


class QueryGenerationError(ValueError):
    """The model did not produce a usable query string."""


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
        tokenizer_kwargs = _tokenizer_compatibility_kwargs(model_dir)
        tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
            trust_remote_code=True,
            **tokenizer_kwargs,
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
            raise QueryGenerationError("model generated an empty query")
        return query


def _tokenizer_compatibility_kwargs(model_dir: Path) -> dict[str, bool]:
    manifest_path = Path(model_dir) / "manifest.json"
    if not manifest_path.is_file():
        return {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("compatibility", {}).get("gemma_legacy_regex") is True:
        # The checkpoint was trained before Transformers changed this regex.
        # Changing it only at inference would change token IDs.
        return {"fix_mistral_regex": False}
    return {}
