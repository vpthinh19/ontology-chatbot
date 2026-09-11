"""Engine chạy trên ontology thật: mỗi kiểu câu hỏi ra đúng mục, dữ kiện có nguồn."""

from __future__ import annotations

import pytest

from ontchatbot.search import EntryKind, SearchEngine, TurtleFileSource
from ontchatbot.settings import ONTOLOGY_PATH


@pytest.fixture(scope="module")
def engine() -> SearchEngine:
    return SearchEngine.open(TurtleFileSource(ONTOLOGY_PATH))


def _nodes(response) -> list[str]:
    return [result.node for result in response.results]


def test_a_procedure_is_found_by_its_name(engine) -> None:
    assert _nodes(engine.search(["nghỉ học tạm thời"]))[0] == ":TemporaryAcademicLeaveProcedure"


def test_an_attribute_is_found_through_its_datatype_property_row(engine) -> None:
    response = engine.search(["điện thoại phòng đào tạo"])

    assert response.results[0].node == ":AcademicManagementUnit"
    assert response.results[0].matched[0].entry.kind is EntryKind.DATATYPE_PROPERTY


def test_a_value_question_finds_every_rule_that_carries_the_value(engine) -> None:
    nodes = _nodes(engine.search(["đăng ký tối đa bao nhiêu tín chỉ"]))

    assert set(nodes[:2]) == {":StandardCreditLoadRule", ":WeakCreditLoadRule"}


def test_a_relation_question_finds_nodes_through_their_object_property_rows(engine) -> None:
    response = engine.search(["thủ tục nộp tại phòng công tác sinh viên"])

    assert response.results
    for result in response.results:
        assert any(
            hit.entry.kind is EntryKind.OBJECT_PROPERTY
            and "nộp tại | Phòng Công tác Chính trị và Sinh viên" in hit.entry.text
            for hit in result.matched
        )


def test_a_document_part_is_found_by_its_coordinates(engine) -> None:
    assert _nodes(engine.search(["Điều 24 quy chế đào tạo"]))[0] == ":Regulation1052Article24"


def test_every_fact_of_a_procedure_carries_its_regulation_source(engine) -> None:
    profile = engine.search(["nghỉ học tạm thời"]).results[0].profile

    assert profile.facts
    for fact in profile.facts:
        assert any("Điều 24" in source.citation for source in fact.sources), fact
