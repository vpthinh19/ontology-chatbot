from __future__ import annotations

from ontchatbot.runtime.generator import QueryGenerationError, QueryGenerator


class _Generator:
    def generate(self, text: str) -> str:
        return text

    def generate_many(self, texts):
        return list(texts)


def _use_generator(generator: QueryGenerator) -> tuple[str, list[str]]:
    return generator.generate("một"), generator.generate_many(["hai", "ba"])


def test_generator_contract_is_independent_of_an_inference_backend() -> None:
    assert _use_generator(_Generator()) == ("một", ["hai", "ba"])


def test_generation_error_remains_a_value_error() -> None:
    assert isinstance(QueryGenerationError("câu hỏi rỗng"), ValueError)
