from __future__ import annotations

from copy import deepcopy

import pytest

from ontchatbot.catalogue import QuerySpec, SlotSpec
from ontchatbot.research.dataset import (
    DatasetError,
    _validate_target_text,
    validate_release,
)
from ontchatbot.research.graph import load_ontology
from ontchatbot.runtime.cards import Card, CardLookup


CATALOGUE = {
    "procedure-source": QuerySpec(
        "procedure-source",
        "procedure",
        "SELECT ?answer WHERE { ${procedure} :basedOn ?part . ?part :officialText ?answer . }",
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
    "credit-load-range": QuerySpec(
        "credit-load-range",
        "academic-rule",
        "SELECT ?answer WHERE { ?rule a :CreditLoadRule ; :minimumCredits ?minimum ; :maximumCredits ?maximum ; :ruleText ?answer . FILTER (?minimum <= ${credits} && ${credits} <= ?maximum) }",
        {"credits": SlotSpec("number")},
    ),
    "no-information": QuerySpec(
        "no-information",
        "out-of-domain",
        "không có thông tin",
        {},
    ),
}
REGISTERS = ("formal", "neutral", "colloquial", "noisy")


LOOKUP = CardLookup(
    [
        Card(
            "procedure-source",
            (procedure,),
            "test",
            f"SELECT ?answer WHERE {{ {procedure} :basedOn ?part . "
            "?part :officialText ?answer . }",
        )
        for procedure in (
            ":TemporaryAcademicLeaveProcedure",
            ":CourseRegistrationProcedure",
        )
    ]
    + [
        Card(
            "credit-load-range",
            (f":Credits{credits}",),
            "test",
            "SELECT ?answer WHERE { ?rule a :CreditLoadRule ; :minimumCredits ?minimum ; "
            ":maximumCredits ?maximum ; :ruleText ?answer . FILTER (?minimum <= "
            f"{credits} && {credits} <= ?maximum) }}",
        )
        for credits in range(15, 23)
    ]
    + [Card("no-information", (), "test", "không có thông tin")]
)


def _valid_release():
    procedure_targets = (
        [":TemporaryAcademicLeaveProcedure"],
        [":CourseRegistrationProcedure"],
    )
    score_targets = tuple(
        [f":Credits{credits}"]
        for credits in ("15", "16", "17", "18", "19", "20", "21", "22")
    )
    questions = {
        "procedure-source": (
            "Xin trình bày quy trình nghỉ học tạm thời",
            "Cách đăng ký học phần gồm những gì",
            "bảo lưu thì làm sao vậy",
            "đkhp kiểu j",
            "Hướng dẫn nghỉ học tạm thời hiện hành",
            "đăng ký môn cho học kỳ mới thế nào",
            "Nêu thủ tục tạm nghỉ chương trình đào tạo",
            "tui muốn chọn hp kỳ tới",
        ),
        "credit-load-range": (
            "Đăng ký 15 tín chỉ thuộc khoảng nào",
            "Mức 16 tín chỉ có hợp lệ không",
            "17 tín chỉ thì áp dụng quy tắc nào",
            "có 18 tín chỉ thuộc mức nào",
            "Xác định quy tắc với 19 tín chỉ",
            "20 tín chỉ được đánh giá thế nào",
            "Cho biết khoảng khi đăng ký 21 tín chỉ",
            "22 tín chỉ là mức gì",
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
        "procedure-source": procedure_targets * 4,
        "credit-load-range": score_targets,
        "no-information": ([],) * 8,
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
    report = validate_release(
        _valid_release(), load_ontology(), CATALOGUE, lookup=LOOKUP
    )

    assert report["records"] == 24
    assert report["domains"] == {
        "academic-rule": 8,
        "out-of-domain": 8,
        "procedure": 8,
    }
    assert report["slot_coverage"]["procedure-source"]["procedure"][
        "missing_train"
    ] == []
    assert report["splits"]["train"]["targets"] > report["splits"]["train"]["queries"]


@pytest.mark.parametrize("target", ([], [":AcademicAdvisor"], [":One", ":Two"]))
def test_target_text_accepts_iri_lists(target: list[str]) -> None:
    _validate_target_text(target, "punctuation-probe")


def test_target_text_rejects_legacy_sparql_string() -> None:
    with pytest.raises(DatasetError, match="list of non-empty IRIs"):
        _validate_target_text("SELECT ?answer WHERE { ?s ?p ?answer }", "bad-target")


def test_rejects_target_that_does_not_match_query_family() -> None:
    release = _valid_release()
    release["train"][0]["target"] = []

    with pytest.raises(DatasetError, match="does not match query family"):
        validate_release(release, load_ontology(), CATALOGUE, lookup=LOOKUP)


def test_rejects_finite_iri_missing_from_train() -> None:
    release = _valid_release()
    course = ":CourseRegistrationProcedure"
    leave = ":TemporaryAcademicLeaveProcedure"
    for row in release["train"]:
        if row["query_id"] == "procedure-source":
            row["target"] = [leave if value == course else value for value in row["target"]]

    with pytest.raises(DatasetError, match="finite slot values missing from train"):
        validate_release(release, load_ontology(), CATALOGUE, lookup=LOOKUP)


def test_rejects_unknown_query_id() -> None:
    release = _valid_release()
    release["train"][0]["query_id"] = "unknown"

    with pytest.raises(DatasetError, match="unknown query_id"):
        validate_release(release, load_ontology(), CATALOGUE, lookup=LOOKUP)


def test_rejects_exact_normalized_cross_split_leakage() -> None:
    release = _valid_release()
    release["test"][0]["input"] = release["train"][0]["input"]

    with pytest.raises(DatasetError, match="inputs cross splits"):
        validate_release(release, load_ontology(), CATALOGUE, lookup=LOOKUP)


def test_near_duplicate_check_is_limited_to_same_query_family() -> None:
    release = _valid_release()
    release["train"][0]["input"] = "Cho biết quy định chính xác dành cho sinh viên khoá 65"
    release["test"][2]["input"] = "Cho biết quy định chính xác dành cho sinh viên khoá 66"

    validate_release(release, load_ontology(), CATALOGUE, lookup=LOOKUP)

    leaked = deepcopy(release)
    leaked["test"][2]["input"] = _valid_release()["test"][2]["input"]
    leaked["test"][0]["input"] = "Cho biết quy định chính xác dành cho sinh viên khoá 66"
    with pytest.raises(DatasetError, match="near-duplicate questions cross splits"):
        validate_release(leaked, load_ontology(), CATALOGUE, lookup=LOOKUP)


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
        lookup=LOOKUP,
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
            lookup=LOOKUP,
        )
