from __future__ import annotations

from types import SimpleNamespace

from ontchatbot.inference import CTranslate2Generator, OntologyChatbot


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

    reply = OntologyChatbot(generator).answer("phòng nào xử lý bảo lưu")

    assert "Phòng Công tác Sinh viên" in reply
