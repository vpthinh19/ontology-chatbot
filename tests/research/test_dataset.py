from __future__ import annotations

from copy import deepcopy

import pytest

from ontchatbot.research.catalogue import QuerySpec, SlotSpec
from ontchatbot.research.dataset import DatasetError, validate_release
from ontchatbot.runtime.sparql import load_ontology


CATALOGUE = {
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
    "performance-band": QuerySpec(
        "performance-band",
        "academic-rule",
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= ${score} && ${score} <= ?maximum) }",
        {"score": SlotSpec("number")},
    ),
    "no-information": QuerySpec(
        "no-information",
        "out-of-domain",
        "không có thông tin",
        {},
    ),
}
REGISTERS = ("formal", "neutral", "colloquial", "noisy")


def _valid_release():
    procedure_targets = (
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
        "SELECT ?answer WHERE { :CourseRegistrationProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
    )
    score_targets = tuple(
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= "
        f"{score} && {score} <= ?maximum) }}"
        for score in ("8.5", "7", "5.5", "3", "9", "6.5", "4.5", "2")
    )
    questions = {
        "procedure-instruction": (
            "Xin trình bày quy trình nghỉ học tạm thời",
            "Cách đăng ký học phần gồm những gì",
            "bảo lưu thì làm sao vậy",
            "đkhp kiểu j",
            "Hướng dẫn nghỉ học tạm thời hiện hành",
            "đăng ký môn cho học kỳ mới thế nào",
            "Nêu thủ tục tạm nghỉ chương trình đào tạo",
            "tui muốn chọn hp kỳ tới",
        ),
        "performance-band": (
            "Điểm trung bình 8.5 được xếp loại nào",
            "Mức 7 điểm thuộc loại gì",
            "5.5 thì kết quả học tập loại nào",
            "có 3 điểm xếp hạng sao",
            "Xếp loại kết quả với điểm 9",
            "6.5 được đánh giá mức nào",
            "Cho biết loại học lực khi đạt 4.5",
            "2 điểm là loại j",
        ),
        "no-information": (
            "Xin chào bạn",
            "Thời tiết hôm nay thế nào",
            "kể tui nghe một câu chuyện",
            "asdf qwer zxcv",
            "Bạn khoẻ không",
            "Ngày mai có mưa không",
            "Gợi ý món ăn tối nay",
            "hello bot nha",
        ),
    }
    release = {"train": [], "val": [], "test": []}
    targets = {
        "procedure-instruction": procedure_targets * 4,
        "performance-band": score_targets,
        "no-information": ("không có thông tin",) * 8,
    }
    offsets = {"train": (0, 4), "val": (4, 6), "test": (6, 8)}
    sequence = 1
    for query_id in CATALOGUE:
        for split, (start, stop) in offsets.items():
            for index in range(start, stop):
                release[split].append(
                    {
                        "id": f"question-{sequence:04d}",
                        "query_id": query_id,
                        "register": REGISTERS[index % 4],
                        "input": questions[query_id][index],
                        "target": targets[query_id][index],
                    }
                )
                sequence += 1
    return release


def test_accepts_dynamic_targets_and_marker() -> None:
    report = validate_release(_valid_release(), load_ontology(), CATALOGUE)

    assert report["records"] == 24
    assert report["domains"] == {
        "academic-rule": 8,
        "out-of-domain": 8,
        "procedure": 8,
    }
    assert report["slot_coverage"]["procedure-instruction"]["procedure"][
        "missing_train"
    ] == []
    assert report["splits"]["train"]["targets"] > report["splits"]["train"]["queries"]


def test_rejects_target_that_does_not_match_query_family() -> None:
    release = _valid_release()
    release["train"][0]["target"] = "không có thông tin"

    with pytest.raises(DatasetError, match="does not match query family"):
        validate_release(release, load_ontology(), CATALOGUE)


def test_rejects_finite_iri_missing_from_train() -> None:
    release = _valid_release()
    course = ":CourseRegistrationProcedure"
    leave = ":TemporaryAcademicLeaveProcedure"
    for row in release["train"]:
        if row["query_id"] == "procedure-instruction":
            row["target"] = row["target"].replace(course, leave)

    with pytest.raises(DatasetError, match="finite slot values missing from train"):
        validate_release(release, load_ontology(), CATALOGUE)


def test_rejects_unknown_query_id() -> None:
    release = _valid_release()
    release["train"][0]["query_id"] = "unknown"

    with pytest.raises(DatasetError, match="unknown query_id"):
        validate_release(release, load_ontology(), CATALOGUE)


def test_rejects_exact_normalized_cross_split_leakage() -> None:
    release = _valid_release()
    release["test"][0]["input"] = release["train"][0]["input"]

    with pytest.raises(DatasetError, match="inputs cross splits"):
        validate_release(release, load_ontology(), CATALOGUE)


def test_near_duplicate_check_is_limited_to_same_query_family() -> None:
    release = _valid_release()
    release["train"][0]["input"] = "Cho biết quy định chính xác dành cho sinh viên khoá 65"
    release["test"][2]["input"] = "Cho biết quy định chính xác dành cho sinh viên khoá 66"

    validate_release(release, load_ontology(), CATALOGUE)

    leaked = deepcopy(release)
    leaked["test"][2]["input"] = _valid_release()["test"][2]["input"]
    leaked["test"][0]["input"] = "Cho biết quy định chính xác dành cho sinh viên khoá 66"
    with pytest.raises(DatasetError, match="near-duplicate questions cross splits"):
        validate_release(leaked, load_ontology(), CATALOGUE)


def test_candidate_mode_allows_unrepresented_catalogue_families() -> None:
    catalogue = {
        **CATALOGUE,
        "procedure-list": QuerySpec(
            "procedure-list",
            "procedure",
            "SELECT ?answer WHERE { ?procedure a :AcademicProcedure ; rdfs:label ?answer . }",
            {},
        ),
    }

    report = validate_release(
        _valid_release(),
        load_ontology(),
        catalogue,
        require_complete_catalogue=False,
    )

    assert report["catalogue_coverage_required"] is False


def test_official_mode_rejects_unrepresented_catalogue_families() -> None:
    catalogue = {
        **CATALOGUE,
        "procedure-list": QuerySpec(
            "procedure-list",
            "procedure",
            "SELECT ?answer WHERE { ?procedure a :AcademicProcedure ; rdfs:label ?answer . }",
            {},
        ),
    }

    with pytest.raises(DatasetError, match="query IDs missing from splits"):
        validate_release(
            _valid_release(),
            load_ontology(),
            catalogue,
            require_complete_catalogue=True,
        )
