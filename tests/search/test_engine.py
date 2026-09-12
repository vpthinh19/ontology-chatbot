"""Engine: từ khoá → thực thể kèm hồ sơ; từ khoá không khớp thì nói rõ."""

from __future__ import annotations

import pytest

from ontchatbot.search import EntryKind, SearchEngine


@pytest.fixture(scope="module")
def engine(mini_source) -> SearchEngine:
    return SearchEngine.open(mini_source)


def test_a_name_question_finds_the_entity_with_that_name(engine) -> None:
    response = engine.search(["nghỉ học tạm thời"])

    assert response.status == "found"
    assert response.results[0].node == ":ThuTucNghiHocTamThoi"
    assert response.results[0].matched[0].entry.kind is EntryKind.LABEL


def test_an_attribute_question_finds_the_entity_that_has_the_attribute(engine) -> None:
    response = engine.search(["điện thoại phòng công tác sinh viên"])

    top = response.results[0]
    assert top.node == ":PhongCongTacSinhVien"
    assert top.matched[0].entry.kind is EntryKind.DATATYPE_PROPERTY


def test_a_relation_question_finds_the_entity_through_its_relation_row(engine) -> None:
    response = engine.search(["thủ tục nộp tại phòng công tác sinh viên"])

    assert any(hit.entry.kind is EntryKind.OBJECT_PROPERTY
               for result in response.results for hit in result.matched)


def test_an_alternative_name_leads_to_the_same_entity(engine) -> None:
    """Tên gọi phụ là cách duy nhất bắc cầu giữa lời người hỏi và tên chính thức."""

    assert engine.search(["bảo lưu kết quả học tập"]).results[0].node == ":ThuTucNghiHocTamThoi"


def test_a_keyword_matching_nothing_is_named_back_to_the_caller(engine) -> None:
    """Mô hình phải biết từ nào không khớp để quyết định hỏi lại hay dừng."""

    response = engine.search(["nghỉ học tạm thời", "bóng đá"])

    assert response.unmatched_keywords == ["bóng đá"]
    assert response.results


def test_nothing_found_is_a_state_not_an_error(engine) -> None:
    response = engine.search(["bóng đá"])

    assert response.status == "not_found"
    assert response.results == []


def test_every_result_carries_its_profile_with_sources(engine) -> None:
    response = engine.search(["nghỉ học tạm thời"])

    profile = response.results[0].profile
    assert profile.label == "Thủ tục nghỉ học tạm thời"
    assert any(source is not None for source, _ in profile.groups)


def test_results_stop_at_top_k(mini_source) -> None:
    engine = SearchEngine.open(mini_source, top_k=1)

    assert len(engine.search(["thủ tục"]).results) == 1


def test_blank_keywords_are_ignored(engine) -> None:
    response = engine.search(["", "   ", "nghỉ học tạm thời"])

    assert response.keywords == ["nghỉ học tạm thời"]
