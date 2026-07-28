from __future__ import annotations

from types import SimpleNamespace

import pytest

from ontchatbot.runtime.gate import GateDecision
from ontchatbot.runtime.model import CTranslate2Generator, _tokenizer_compatibility_kwargs
from ontchatbot.runtime.pipeline import OntologyChatbot, OutOfScopeError


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
        return " SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . } "


class _Translator:
    def __init__(self) -> None:
        self.call = None

    def translate_batch(self, tokens, **kwargs):
        self.call = (tokens, kwargs)
        return [SimpleNamespace(hypotheses=[["t3", "t4"]])]


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


def test_chatbot_connects_generated_query_to_ontology() -> None:
    query = (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?node . "
        "?node rdfs:label ?answer . }"
    )
    generator = SimpleNamespace(generate=lambda _: query)
    gate = SimpleNamespace(decide=lambda _: GateDecision(True, 0.99))

    reply = OntologyChatbot(generator, gate).answer("phòng nào xử lý bảo lưu")

    assert "Phòng Công tác Chính trị và Sinh viên" in reply


def test_chatbot_does_not_generate_query_when_gate_rejects() -> None:
    calls = []
    generator = SimpleNamespace(generate=lambda question: calls.append(question))
    gate = SimpleNamespace(decide=lambda _: GateDecision(False, 0.02))

    with pytest.raises(OutOfScopeError):
        OntologyChatbot(generator, gate).answer("thời tiết hôm nay")

    assert calls == []


def test_gemma_artifact_preserves_training_tokenizer_regex(tmp_path) -> None:
    (tmp_path / "manifest.json").write_text(
        '{"compatibility":{"gemma_legacy_regex":true}}', encoding="utf-8"
    )

    assert _tokenizer_compatibility_kwargs(tmp_path) == {
        "fix_mistral_regex": False
    }
