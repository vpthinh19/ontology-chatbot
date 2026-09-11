"""Chỉ mục BM25: tìm theo từ, không tìm thấy thì rỗng, lưu rồi nạp lại không đổi."""

from __future__ import annotations

from ontchatbot.search import IndexBuilder, SearchIndex, TextAnalyzer


def _index(ontology, fingerprint="phien-ban-1") -> SearchIndex:
    return SearchIndex.build(IndexBuilder(ontology).build_entries(), TextAnalyzer(), fingerprint)


def test_rows_sharing_the_keyword_words_rank_first(mini_ontology) -> None:
    hits = _index(mini_ontology).search("điện thoại phòng công tác sinh viên")

    assert hits[0].entry.text == "Phòng Công tác Chính trị và Sinh viên | điện thoại"
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


def test_saved_index_loads_back_with_the_same_results(mini_ontology, tmp_path) -> None:
    index = _index(mini_ontology)
    index.save(tmp_path)

    loaded = SearchIndex.load(tmp_path, TextAnalyzer())

    assert loaded.fingerprint == "phien-ban-1"
    assert loaded.entries == index.entries
    before = [(hit.entry, round(hit.score, 6)) for hit in index.search("nghỉ học tạm thời")]
    after = [(hit.entry, round(hit.score, 6)) for hit in loaded.search("nghỉ học tạm thời")]
    assert before == after
