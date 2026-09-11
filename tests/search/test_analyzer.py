"""Tách từ: âm tiết cộng từ ghép, bỏ từ hỏi, không để dấu câu dính vào từ."""

from __future__ import annotations

from ontchatbot.search import TextAnalyzer


class _FixedSegmenter:
    """Bộ tách từ giả, trả đúng các từ ghép đã định cho từng đoạn."""

    name = "fixed"

    def __init__(self, segments: dict[str, list[str]]) -> None:
        self.segments = segments
        self.calls: list[str] = []

    def segment(self, text: str) -> list[str]:
        self.calls.append(text.strip())
        return self.segments.get(text.strip(), text.split())


def test_tokens_combine_compound_words_with_single_syllables() -> None:
    analyzer = TextAnalyzer(_FixedSegmenter({"Nghỉ học tạm thời": ["Nghỉ_học", "tạm_thời"]}))

    assert analyzer.tokens("Nghỉ học tạm thời") == ["nghỉ_học", "tạm_thời", "nghỉ", "học", "tạm", "thời"]


def test_compounds_made_only_of_question_words_are_dropped() -> None:
    analyzer = TextAnalyzer(_FixedSegmenter({"tín chỉ bao nhiêu": ["tín_chỉ", "bao_nhiêu"]}))

    assert analyzer.compounds("tín chỉ bao nhiêu") == ["tín_chỉ"]
    assert analyzer.syllables("tín chỉ bao nhiêu") == ["tín", "chỉ"]


def test_punctuation_splits_the_text_before_segmentation() -> None:
    """Dấu phân cách của dòng chỉ mục không được dính vào từ, kiểu "|_phòng"."""

    segmenter = _FixedSegmenter({})
    TextAnalyzer(segmenter).compounds("Thủ tục thôi học | nộp tại | Phòng Công tác Chính trị và Sinh viên")

    assert segmenter.calls == ["Thủ tục thôi học", "nộp tại", "Phòng Công tác Chính trị và Sinh viên"]


def test_terms_keep_each_word_once() -> None:
    analyzer = TextAnalyzer(_FixedSegmenter({}))

    assert analyzer.terms("học lại | có bước | học lại - bước 1") == ["học", "lại", "bước", "1"]


def test_the_default_segmenter_joins_vietnamese_compound_words() -> None:
    analyzer = TextAnalyzer()

    assert "tạm_thời" in analyzer.compounds("Thủ tục nghỉ học tạm thời")
    assert "thời_tiết" in analyzer.compounds("thời tiết nha trang")
    assert analyzer.name == "syllables+underthesea"
