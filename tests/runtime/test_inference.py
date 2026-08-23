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

from ontchatbot.catalogue import load_catalogue
from ontchatbot.settings import QUERY_CATALOGUE_PATH
from ontchatbot.runtime.pipeline import OntologyChatbot
from ontchatbot.runtime.render import NO_INFORMATION_REPLY
from ontchatbot.runtime.sparql import SparqlError


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


def test_batch_lookup_logs_the_label_each_keyword_landed_on(caplog) -> None:
    """Một từ khoá trượt và một từ khoá trúng phải phân biệt được trong nhật ký.

    Số dòng lấy về không nói lên nguyên nhân. Nhãn mới nói: trúng nhãn nào, hay
    trượt vì model bảo không có thông tin.
    """

    query = _procedure_target()
    generator = SimpleNamespace(
        generate_many=lambda questions: [query, "không có thông tin"]
    )

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline"):
        OntologyChatbot(generator).answer_many(["bảo lưu", "thời tiết hôm nay"])

    trace = "\n".join(record.getMessage() for record in caplog.records)
    assert "keyword='bảo lưu' label=academic-procedure-facts" in trace
    assert "keyword='thời tiết hôm nay' label=no-information rows=0" in trace


def test_batch_lookup_labels_a_query_that_belongs_to_no_family(caplog) -> None:
    outside = "SELECT ?x WHERE { ?x a <http://example.org/Nothing> }"
    generator = SimpleNamespace(generate_many=lambda questions: [outside])

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline"):
        OntologyChatbot(generator).answer_many(["bảo lưu"])

    trace = "\n".join(record.getMessage() for record in caplog.records)
    assert "keyword='bảo lưu' label=off-catalogue rows=0" in trace


def test_batch_lookup_rejects_a_call_with_no_usable_keyword() -> None:
    """Danh sách toàn khoảng trắng phải thành lỗi công cụ hiểu được.

    Trợ lý bắt ``SparqlError`` rồi trả lời là không tìm thấy. Một lỗi khác loại
    thoát ra và làm hỏng cả lượt gọi công cụ.
    """

    generator = SimpleNamespace(generate_many=lambda questions: [])

    with pytest.raises(SparqlError):
        OntologyChatbot(generator).answer_many(["   ", ""])

