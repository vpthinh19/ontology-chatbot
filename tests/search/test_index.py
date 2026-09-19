"""Chỉ mục BM25: tìm theo từ, không tìm thấy thì rỗng."""

from __future__ import annotations

from ontchatbot.search import IndexBuilder, SearchIndex, TextAnalyzer


def _index(ontology) -> SearchIndex:
    return SearchIndex(IndexBuilder(ontology).build_entries(), TextAnalyzer())


def test_rows_sharing_the_keyword_words_rank_first(mini_ontology) -> None:
    hits = _index(mini_ontology).search("điện thoại phòng công tác sinh viên")

    assert hits[0].entry.text == "Phòng Công tác sinh viên | điện thoại"
    assert all(hit.score > 0 for hit in hits)
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


def test_a_keyword_without_shared_words_finds_nothing(mini_ontology) -> None:
    index = _index(mini_ontology)

    assert index.search("bóng đá") == []
    assert index.search("là gì") == []  # chỉ toàn từ hỏi


def test_matching_is_per_syllable_so_a_shared_syllable_is_enough(mini_ontology) -> None:
    """Tách theo âm tiết: "thời tiết" có chung "thời" với "tạm thời" nên vẫn ra dòng.

    Engine không đoán nghĩa; loại bỏ mục lạc đề là việc của bước kiểm ``dong_khop``.
    """

    assert _index(mini_ontology).search("thời tiết")

