"""Tách chữ thành từ: âm tiết, bỏ từ hỏi, mỗi từ đếm một lần."""

from __future__ import annotations

from ontchatbot.search import TextAnalyzer


def test_text_becomes_lowercase_syllables() -> None:
    assert TextAnalyzer().terms("Nghỉ Học Tạm Thời") == ["nghỉ", "học", "tạm", "thời"]


def test_question_words_are_dropped_from_both_sides() -> None:
    """Bỏ ở cả dòng chỉ mục lẫn từ khoá, nên hai bên vẫn khớp nhau."""

    analyzer = TextAnalyzer()

    assert analyzer.terms("học phí là bao nhiêu") == ["học", "phí"]
    assert analyzer.terms("nộp đơn ở đâu") == ["nộp", "đơn"]


def test_punctuation_never_becomes_part_of_a_word() -> None:
    assert TextAnalyzer().terms("nghỉ học | nộp tại | Phòng CTSV") == [
        "nghỉ", "học", "nộp", "phòng", "ctsv"
    ]


def test_each_word_is_counted_once_per_row() -> None:
    """Dòng quan hệ hay lặp chữ ở hai đầu. Đếm lặp thì dòng đó ăn điểm hai lần cho
    cùng một chữ và đè lên dòng tên chính."""

    assert TextAnalyzer().terms("nghỉ học tạm thời | có bước | nghỉ học tạm thời") == [
        "nghỉ", "học", "tạm", "thời", "bước"
    ]


def test_the_analyzer_names_itself_so_a_saved_index_is_not_mixed_up() -> None:
    assert TextAnalyzer().name == "syllables"


def test_an_empty_or_symbol_only_keyword_yields_no_terms() -> None:
    analyzer = TextAnalyzer()

    assert analyzer.terms("") == []
    assert analyzer.terms("!!! ???") == []
