from __future__ import annotations


def _procedure_target() -> str:
    """Đích chuẩn lấy thẳng từ danh mục - xem ghi chú ở test_catalogue_guard."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    return catalogue["academic-procedure-facts"].target_template.replace(
        "${anchor}", ":TemporaryAcademicLeaveProcedure"
    )

import logging
from types import SimpleNamespace

import pytest

from ontchatbot.runtime.model import MAX_TARGET_LENGTH, CTranslate2Generator
from ontchatbot.catalogue import load_catalogue
from ontchatbot.settings import QUERY_CATALOGUE_PATH
from ontchatbot.runtime.pipeline import OntologyChatbot
from ontchatbot.runtime.render import NO_INFORMATION_REPLY


class _Tokenizer:
    def __init__(self) -> None:
        self.seen = None

    def encode(self, text, **kwargs):
        self.seen = (text, kwargs)
        return SimpleNamespace(tokens=["t1", "t2"])

    def token_to_id(self, token):
        return int(token[1:])

    def decode(self, ids, **kwargs):
        return " SELECT DISTINCT ?answer WHERE { :TemporaryAcademicLeaveProcedure :hasStep ?part . ?part :stepText ?answer . } "


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
        {
            "beam_size": 1,
            "max_decoding_length": MAX_TARGET_LENGTH,
            "max_batch_size": 1,
        },
    )
    assert query.startswith("SELECT")


def test_ctranslate_generator_uses_specific_error_for_empty_output() -> None:
    generator = CTranslate2Generator(_Translator(), _EmptyTokenizer())

    with pytest.raises(ValueError) as error:
        generator.generate("học phí")

    assert type(error.value).__name__ == "QueryGenerationError"
    assert str(error.value) == "model generated an empty query"


def test_chatbot_connects_generated_query_to_ontology() -> None:
    query = _procedure_target()
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
    query = _procedure_target()
    generator = SimpleNamespace(generate=lambda _: query)

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline"):
        reply = OntologyChatbot(generator).answer("phòng nào xử lý bảo lưu")

    trace = "\n".join(record.getMessage() for record in caplog.records)
    assert f"model output={query!r}" in trace
    # Khuôn dump trả cả chục dòng chứ không phải một; chốt con số cứng là chốt
    # ảnh chụp của một lần dựng danh mục. Điều cần canh là nhật ký CÓ ghi số
    # dòng, và ghi một số dương.
    assert "ontology rows=" in trace
    assert "ontology rows=0" not in trace
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


def test_one_keyword_answers_the_same_whatever_it_is_sent_with() -> None:
    """Kết quả của một cụm từ khoá không được đổi theo cụm đi kèm.

    Gộp lô thật sự thì đệm mọi câu về cùng độ dài, và token gần ngang điểm lật
    theo thứ tự cộng dồn - cùng một cụm cho ra truy vấn khác nhau tuỳ hàng xóm.
    """

    from ontchatbot.runtime.model import CTranslate2Generator

    calls = []

    class _Translator:
        def translate_batch(self, batch, **kwargs):
            calls.append(kwargs)
            return [_Result(["x"]) for _ in batch]

    class _Result:
        def __init__(self, tokens):
            self.hypotheses = [tokens]

    class _Tokenizer:
        def encode(self, text, add_special_tokens=True):
            return type("E", (), {"tokens": [text]})()

        def token_to_id(self, token):
            return 1

        def decode(self, ids, skip_special_tokens=True):
            return "SELECT ?x WHERE { ?x ?y ?z }"

    generator = CTranslate2Generator(_Translator(), _Tokenizer())
    generator.generate_many(["học bổng", "học bổng khuyến khích học tập"])

    assert calls[0]["max_batch_size"] == 1
