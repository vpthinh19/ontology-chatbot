from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from ontchatbot.runtime.model import CTranslate2Generator, _tokenizer_compatibility_kwargs
from ontchatbot.runtime.pipeline import OntologyChatbot
from ontchatbot.runtime.render import NO_INFORMATION_REPLY


class _Tokenizer:
    def __init__(self) -> None:
        self.seen = None

    def __call__(self, text, **kwargs):
        self.seen = (text, kwargs)
        return SimpleNamespace(input_ids=[1, 2])

    def convert_ids_to_tokens(self, ids):
        return [f"t{token_id}" for token_id in ids]

    def convert_tokens_to_ids(self, tokens):
        return [int(token[1:]) for token in tokens]

    def decode(self, ids, **kwargs):
        return " SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . } "


class _Translator:
    def __init__(self) -> None:
        self.call = None

    def translate_batch(self, tokens, **kwargs):
        self.call = (tokens, kwargs)
        return [SimpleNamespace(hypotheses=[["t3", "t4"]])]


class _EmptyTokenizer(_Tokenizer):
    def decode(self, ids, **kwargs):
        return " "


def test_ctranslate_generator_normalizes_and_greedily_decodes() -> None:
    tokenizer = _Tokenizer()
    translator = _Translator()
    generator = CTranslate2Generator(translator, tokenizer)

    query = generator.generate("  tui đi NVQS, mún bảo lưu  ")

    assert tokenizer.seen[0] == "tui đi nghĩa vụ quân sự, muốn bảo lưu"
    assert translator.call == (
        [["t1", "t2"]],
        {"beam_size": 1, "max_decoding_length": 160},
    )
    assert query.startswith("SELECT ?answer")


def test_ctranslate_generator_uses_specific_error_for_empty_output() -> None:
    generator = CTranslate2Generator(_Translator(), _EmptyTokenizer())

    with pytest.raises(ValueError) as error:
        generator.generate("học phí")

    assert type(error.value).__name__ == "QueryGenerationError"
    assert str(error.value) == "model generated an empty query"


def test_chatbot_connects_generated_query_to_ontology() -> None:
    query = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?node . "
        "?node rdfs:label ?answer . }"
    )
    generator = SimpleNamespace(generate=lambda _: query)

    reply = OntologyChatbot(generator).answer("phòng nào xử lý bảo lưu")

    assert "Phòng Công tác Chính trị và Sinh viên" in reply


def test_chatbot_returns_no_information_for_model_marker() -> None:
    generator = SimpleNamespace(generate=lambda _: " không có thông tin ")

    reply = OntologyChatbot(generator).answer("thời tiết hôm nay")

    assert reply == NO_INFORMATION_REPLY


def test_chatbot_logs_model_marker_decision(caplog) -> None:
    generator = SimpleNamespace(generate=lambda _: "không có thông tin")

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline"):
        reply = OntologyChatbot(generator).answer("hc phí k65 cntt")

    trace = "\n".join(record.getMessage() for record in caplog.records)
    assert "input='hc phí k65 cntt'" in trace
    assert "normalized='học phí khoá 65 công nghệ thông tin'" in trace
    assert "model output='không có thông tin'" in trace
    assert f"reply={reply!r}" in trace
    assert "ontology rows=" not in trace


def test_chatbot_logs_generated_sparql_ontology_rows_and_reply(caplog) -> None:
    query = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?node . "
        "?node rdfs:label ?answer . }"
    )
    generator = SimpleNamespace(generate=lambda _: query)

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline"):
        reply = OntologyChatbot(generator).answer("phòng nào xử lý bảo lưu")

    trace = "\n".join(record.getMessage() for record in caplog.records)
    assert f"model output={query!r}" in trace
    assert "ontology rows=1" in trace
    assert f"reply={reply!r}" in trace
    assert "total_ms=" in trace


def test_chatbot_logs_failing_stage_with_traceback(caplog) -> None:
    def fail(_: str) -> str:
        raise RuntimeError("boom")

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline"):
        with pytest.raises(RuntimeError, match="boom"):
            OntologyChatbot(SimpleNamespace(generate=fail)).answer("bảo lưu")

    error = next(record for record in caplog.records if record.levelno == logging.ERROR)
    assert "stage=generator" in error.getMessage()
    assert error.exc_info is not None


def test_gemma_artifact_preserves_training_tokenizer_regex(tmp_path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"compatibility":{"gemma_legacy_regex":true}}', encoding="utf-8"
    )

    assert _tokenizer_compatibility_kwargs(tmp_path) == {
        "fix_mistral_regex": False
    }
