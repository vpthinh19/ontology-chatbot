"""Engine: từ khoá → node kèm hồ sơ; từ khoá không khớp; chỉ mục cũ bị từ chối."""

from __future__ import annotations

import shutil

import pytest

from ontchatbot.search import (
    EntryKind,
    IndexBuilder,
    SearchEngine,
    SearchIndex,
    StaleIndexError,
    TextAnalyzer,
    TurtleFileSource,
)


@pytest.fixture(scope="module")
def engine(mini_source) -> SearchEngine:
    return SearchEngine.open(mini_source)


def test_an_attribute_question_finds_the_node_that_has_the_attribute(engine) -> None:
    response = engine.search(["điện thoại phòng công tác sinh viên"])

    top = response.results[0]
    assert response.status == "found"
    assert top.node == ":StudentAffairsOffice"
    assert top.matched[0].entry.kind is EntryKind.DATATYPE_PROPERTY
    assert top.profile.label == "Phòng Công tác Chính trị và Sinh viên"


def test_keywords_that_match_nothing_are_reported(engine) -> None:
    response = engine.search(["nghỉ học tạm thời", "bóng đá"])

    assert response.results[0].node == ":LeaveProcedure"
    assert response.unmatched_keywords == ["bóng đá"]


def test_no_match_at_all_means_no_information(engine) -> None:
    response = engine.search(["bóng đá"])

    assert response.status == "not_found"
    assert response.results == []


def test_keywords_are_trimmed_and_deduplicated(engine) -> None:
    response = engine.search(["  nghỉ học tạm thời ", "nghỉ học tạm thời", ""])

    assert response.keywords == ["nghỉ học tạm thời"]


def test_top_k_limits_the_number_of_nodes(mini_source) -> None:
    response = SearchEngine.open(mini_source, top_k=1).search(["sinh viên"])

    assert len(response.results) == 1


def test_a_saved_index_is_rejected_once_the_ontology_changes(mini_source, mini_ontology, tmp_path) -> None:
    index_directory = tmp_path / "index"
    SearchIndex.build(
        IndexBuilder(mini_ontology).build_entries(), TextAnalyzer(), mini_source.fingerprint()
    ).save(index_directory)

    same = SearchEngine.open(mini_source, index_directory=index_directory)
    assert same.search(["nghỉ học tạm thời"]).results[0].node == ":LeaveProcedure"

    changed_path = tmp_path / "changed.ttl"
    shutil.copy(mini_source.path, changed_path)
    with open(changed_path, "a", encoding="utf-8") as handle:
        handle.write('\n:Student <http://www.w3.org/2004/02/skos/core#altLabel> "người học"@vi .\n')
    with pytest.raises(StaleIndexError):
        SearchEngine.open(TurtleFileSource(changed_path), index_directory=index_directory)
