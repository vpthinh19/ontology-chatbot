from __future__ import annotations

import pytest

from ontchatbot.research.benchmark import BenchmarkError, validate_benchmark
from ontchatbot.research.catalogue import QuerySpec, SlotSpec
from ontchatbot.runtime.sparql import load_ontology


CATALOGUE = {
    "performance-band": QuerySpec(
        "performance-band",
        "academic-rule",
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= ${score} && ${score} <= ?maximum) }",
        {"score": SlotSpec("number")},
    ),
    "procedure-instruction": QuerySpec(
        "procedure-instruction",
        "procedure",
        "SELECT ?answer WHERE { ${procedure} :instructionProvision ?part . ?part :officialText ?answer . }",
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


def test_accepts_held_out_numeric_target_and_marker() -> None:
    training = [
        _row(
            "train-1",
            "performance-band",
            "8.5 được loại gì",
            "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= 8.5 && 8.5 <= ?maximum) }",
        ),
        _row("train-2", "no-information", "xin chào", "không có thông tin"),
    ]
    benchmark = [
        _row(
            "test-1",
            "performance-band",
            "Nếu được bảy điểm thì xếp mức nào",
            "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= 7 && 7 <= ?maximum) }",
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

    row["query_id"] = "performance-band"
    with pytest.raises(BenchmarkError, match="does not match query family"):
        validate_benchmark([row], load_ontology(), catalogue=CATALOGUE)


def test_rejects_finite_iri_not_seen_in_train() -> None:
    target = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure "
        ":instructionProvision ?part . ?part :officialText ?answer . }"
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
