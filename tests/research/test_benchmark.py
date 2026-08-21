from __future__ import annotations

from pathlib import Path

import pytest

from ontchatbot.research.benchmark import (
    BenchmarkError,
    load_benchmark,
    load_user_query_expectations,
    validate_benchmark,
)
from ontchatbot.catalogue import QuerySpec, SlotSpec
from ontchatbot.runtime.sparql import load_ontology


CATALOGUE = {
    "credit-load-range": QuerySpec(
        "credit-load-range",
        "academic-rule",
        "SELECT ?answer WHERE { ?rule a :CreditLoadRule ; :minimumCredits ?minimum ; :maximumCredits ?maximum ; :ruleText ?answer . FILTER (?minimum <= ${credits} && ${credits} <= ?maximum) }",
        {"credits": SlotSpec("number")},
    ),
    "procedure-instruction": QuerySpec(
        "procedure-instruction",
        "procedure",
        "SELECT ?answer WHERE { ${procedure} :hasStep ?part . ?part :stepText ?answer . }",
        {
            "procedure": SlotSpec(
                "iri",
                (
                    ":TemporaryAcademicLeaveProcedure",
                    ":CourseRegistrationProcedure",
                ),
            )
        },
    ),
    "no-information": QuerySpec(
        "no-information", "out-of-domain", "không có thông tin", {}
    ),
}


def _row(identifier, query_id, text, target):
    return {
        "id": identifier,
        "query_id": query_id,
        "register": "neutral",
        "input": text,
        "target": target,
    }


def test_real_user_cases_keep_every_declared_expectation() -> None:
    """Bộ câu hỏi do người dùng cung cấp phải giữ đủ mọi kỳ vọng đã khai báo.

    Ngưỡng tối thiểu cho phép bổ sung trường hợp mới nhưng phát hiện việc mất
    dữ liệu đánh giá.
    """

    expectations = load_user_query_expectations()

    assert len(expectations) >= 15
    # ``note`` ghi lý do chọn nhãn cho các kỳ vọng cần diễn giải; trường này là
    # tuỳ chọn để giữ tương thích với các kỳ vọng chỉ cần câu hỏi và nhãn.
    assert all(
        {"question", "expected_query_id"} <= set(item) <= {"question", "expected_query_id", "note"}
        for item in expectations
    )


def test_accepts_held_out_numeric_target_and_marker() -> None:
    training = [
        _row(
            "train-1",
            "credit-load-range",
            "18 tín chỉ thuộc khoảng nào",
            "SELECT ?answer WHERE { ?rule a :CreditLoadRule ; :minimumCredits ?minimum ; :maximumCredits ?maximum ; :ruleText ?answer . FILTER (?minimum <= 18 && 18 <= ?maximum) }",
        ),
        _row("train-2", "no-information", "xin chào", "không có thông tin"),
    ]
    benchmark = [
        _row(
            "test-1",
            "credit-load-range",
            "Nếu đăng ký 17 tín chỉ thì thuộc khoảng nào",
            "SELECT ?answer WHERE { ?rule a :CreditLoadRule ; :minimumCredits ?minimum ; :maximumCredits ?maximum ; :ruleText ?answer . FILTER (?minimum <= 17 && 17 <= ?maximum) }",
        ),
        _row("test-2", "no-information", "mai trời mưa không", "không có thông tin"),
    ]

    report = validate_benchmark(
        benchmark,
        load_ontology(),
        catalogue=CATALOGUE,
        training_rows=training,
    )

    assert report["records"] == 2
    assert report["queries_supported_by_train"] == 2
    assert report["domains"] == {"academic-rule": 1, "out-of-domain": 1}


def test_rejects_unknown_query_or_mismatched_target() -> None:
    row = _row("test-1", "unknown", "một câu mới", "không có thông tin")
    with pytest.raises(BenchmarkError, match="unknown query_id"):
        validate_benchmark([row], load_ontology(), catalogue=CATALOGUE)

    row["query_id"] = "credit-load-range"
    with pytest.raises(BenchmarkError, match="does not match query family"):
        validate_benchmark([row], load_ontology(), catalogue=CATALOGUE)


def test_rejects_finite_iri_not_seen_in_train() -> None:
    target = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure "
        ":hasStep ?part . ?part :stepText ?answer . }"
    )
    training = [_row("train-1", "procedure-instruction", "bảo lưu sao", target)]
    benchmark = [
        _row(
            "test-1",
            "procedure-instruction",
            "đăng ký môn như nào",
            target.replace(
                ":TemporaryAcademicLeaveProcedure", ":CourseRegistrationProcedure"
            ),
        )
    ]

    with pytest.raises(BenchmarkError, match="finite slot values absent from train"):
        validate_benchmark(
            benchmark,
            load_ontology(),
            catalogue=CATALOGUE,
            training_rows=training,
        )


def test_rejects_training_question_leak() -> None:
    row = _row("test-1", "no-information", "xin chào", "không có thông tin")

    with pytest.raises(BenchmarkError, match="leaks from training"):
        validate_benchmark(
            [row],
            load_ontology(),
            catalogue=CATALOGUE,
            training_rows=[{**row, "id": "train-1"}],
        )
