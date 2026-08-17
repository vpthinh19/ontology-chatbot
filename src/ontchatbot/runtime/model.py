"""Minimal CTranslate2 inference pipeline for direct SPARQL generation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .text import normalize_model_input

MAX_SOURCE_LENGTH = 128
# Keep deployed CTranslate2 decoding aligned with the training/evaluation
# protocol. The target limit of 320 tokens includes room for EOS.
MAX_TARGET_LENGTH = 320


class QueryGenerator(Protocol):
    def generate(self, text: str) -> str: ...

    def generate_many(self, texts: Sequence[str]) -> list[str]: ...


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
            from tokenizers import Tokenizer
        except ImportError as exc:  # pragma: no cover - requires inference extra.
            raise RuntimeError("install the inference extra to load a model") from exc

        model_dir = Path(model_dir)
        if not (model_dir / "model.bin").is_file():
            raise FileNotFoundError(f"CTranslate2 model not found: {model_dir}")
        tokenizer_path = model_dir / "tokenizer.json"
        if not tokenizer_path.is_file():
            raise FileNotFoundError(f"Tokenizer not found: {tokenizer_path}")
        tokenizer = Tokenizer.from_file(str(tokenizer_path))
        tokenizer.no_padding()
        tokenizer.enable_truncation(max_length=MAX_SOURCE_LENGTH)
        translator = ctranslate2.Translator(
            str(model_dir),
            device=device,
            compute_type=compute_type,
        )
        return cls(translator, tokenizer)

    def generate_many(self, texts: Sequence[str]) -> list[str]:
        """Sinh cho nhiều câu một lượt, giữ nguyên thứ tự đưa vào.

        Luôn dùng ``translate_batch`` để thực hiện suy luận theo lô.
        """

        sources = [normalize_model_input(text) for text in texts]
        if any(not source for source in sources):
            raise ValueError("question is empty")
        if not sources:
            return []
        batch = [
            self._tokenizer.encode(source, add_special_tokens=True).tokens
            for source in sources
        ]
        results = self._translator.translate_batch(
            batch,
            beam_size=1,
            max_decoding_length=MAX_TARGET_LENGTH,
        )
        return [self._decode(result) for result in results]

    def generate(self, text: str) -> str:
        return self.generate_many([text])[0]

    def _decode(self, result) -> str:
        target_ids = []
        for token in result.hypotheses[0]:
            token_id = self._tokenizer.token_to_id(token)
            if token_id is None:
                raise QueryGenerationError(
                    "model generated a token outside the vocabulary"
                )
            target_ids.append(token_id)
        query = self._tokenizer.decode(target_ids, skip_special_tokens=True).strip()
        if not query:
            raise QueryGenerationError("model generated an empty query")
        return query
