from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest
from rdflib import Graph

from ontchatbot.catalogue import load_catalogue
from ontchatbot.settings import QUERY_CATALOGUE_PATH
from ontchatbot.runtime.pipeline import (
    Classification,
    OntologyChatbot,
    freeze_rows,
)
from ontchatbot.runtime.render import NO_INFORMATION_REPLY
from ontchatbot.runtime.sparql import SparqlError


def _procedure_target() -> str:
    """Đích chuẩn lấy thẳng từ danh mục - xem ghi chú ở test_catalogue_guard."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    return catalogue["academic-procedure-facts"].target_template.replace(
        "${anchor}", ":TemporaryAcademicLeaveProcedure"
    )


def _two_targets_from_one_catalogue_family() -> tuple[str, str]:
    """Hai truy vấn hợp lệ, cụ thể từ một họ có slot với hai giá trị."""

    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    spec = catalogue["payment-fee-by-method"]
    slot = spec.slots["phuongthuc"]
    first, second = slot.values[:2]
    return (
        spec.target_template.replace("${phuongthuc}", first),
        spec.target_template.replace("${phuongthuc}", second),
    )


def test_pipeline_classifies_normalized_model_inputs_once() -> None:
    seen = []
    generator = SimpleNamespace(
        generate_many=lambda values: seen.append(tuple(values)) or [_procedure_target()]
    )
    chatbot = OntologyChatbot(generator)
    prepared = chatbot.prepare_keywords(["  đk học phần  "])

    choices = chatbot.classify_many([item.model_input for item in prepared])

    assert prepared[0].original == "đk học phần"
    assert prepared[0].model_input == "đăng ký học phần"
    assert seen == [("đăng ký học phần",)]
    assert choices[0].query == _procedure_target()


def test_two_concrete_queries_in_one_family_remain_distinct() -> None:
    first, second = _two_targets_from_one_catalogue_family()
    chatbot = OntologyChatbot(
        SimpleNamespace(generate_many=lambda _: [first, second])
    )

    choices = chatbot.classify_many(["một", "hai"])

    assert choices[0].label == choices[1].label
    assert choices[0].query != choices[1].query


def test_batch_executes_duplicate_concrete_query_once(monkeypatch) -> None:
    query = "SELECT ?answer WHERE { :Example :value ?answer . }"
    executed = []

    def execute(_graph, concrete_query):
        executed.append(concrete_query)
        return [{"answer": "A"}]

    monkeypatch.setattr("ontchatbot.runtime.pipeline.execute_select", execute)
    chatbot = OntologyChatbot(
        SimpleNamespace(generate_many=lambda _: [query, query]),
        graph=Graph(),
        catalogue={},
    )

    chatbot.answer_many(["một", "hai"])

    assert executed == [query]


def test_empty_and_failed_queries_are_distinct_before_both_render_as_missed(
    monkeypatch,
) -> None:
    def execute(_graph, query):
        if query == "empty":
            return []
        raise SparqlError("invalid query")

    monkeypatch.setattr("ontchatbot.runtime.pipeline.execute_select", execute)
    chatbot = OntologyChatbot(SimpleNamespace(), graph=Graph(), catalogue={})
    empty = chatbot.execute_query("empty")
    failed = chatbot.execute_query("failed")
    prepared = chatbot.prepare_keywords(["không có hàng", "truy vấn hỏng"])

    rendered = chatbot.render_many(
        prepared,
        [Classification("unchecked", "empty"), Classification("unchecked", "failed")],
        {"empty": empty, "failed": failed},
    )

    assert empty.status == "ok"
    assert failed.status == "query-failed"
    assert json.loads(rendered)["tu_khoa_khong_thay"] == [
        "không có hàng",
        "truy vấn hỏng",
    ]


def test_frozen_rows_preserve_column_order_and_primitive_types() -> None:
    frozen = freeze_rows(
        [{"second": 7, "first": False, "fraction": 1.25, "empty": None}]
    )

    assert frozen == ((
        ("second", 7),
        ("first", False),
        ("fraction", 1.25),
        ("empty", None),
    ),)


def test_execute_query_propagates_unexpected_errors(monkeypatch) -> None:
    def execute(_graph, _query):
        raise RuntimeError("database disconnected")

    monkeypatch.setattr("ontchatbot.runtime.pipeline.execute_select", execute)
    chatbot = OntologyChatbot(SimpleNamespace(), graph=Graph(), catalogue={})

    with pytest.raises(RuntimeError, match="database disconnected"):
        chatbot.execute_query("SELECT ?answer WHERE { :Example :value ?answer . }")


def test_off_catalogue_output_never_executes_sparql(monkeypatch) -> None:
    executed = []

    def execute(_graph, query):
        executed.append(query)
        return []

    monkeypatch.setattr("ontchatbot.runtime.pipeline.execute_select", execute)
    chatbot = OntologyChatbot(
        SimpleNamespace(
            generate_many=lambda _: [
                "SELECT ?answer WHERE { :Example :value ?answer . }"
            ]
        ),
        graph=Graph(),
    )

    chatbot.answer_many(["không có trong danh mục"])

    assert executed == []


def test_mixed_found_and_missed_batch_output_keeps_the_render_contract(monkeypatch) -> None:
    query = "SELECT ?answer WHERE { :Example :value ?answer . }"
    monkeypatch.setattr(
        "ontchatbot.runtime.pipeline.execute_select",
        lambda _graph, _query: [{"answer": "Dữ kiện"}],
    )
    chatbot = OntologyChatbot(
        SimpleNamespace(generate_many=lambda _: [query, "không có thông tin"]),
        graph=Graph(),
        catalogue={},
    )

    rendered = json.loads(chatbot.answer_many(["có dữ kiện", "không có dữ kiện"]))

    assert rendered["trang_thai"] == "co_du_lieu"
    assert rendered["du_lieu"] == [{"answer": "Dữ kiện"}]
    assert rendered["tu_khoa_khong_thay"] == ["không có dữ kiện"]


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
