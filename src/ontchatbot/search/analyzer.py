"""Tách chữ thành từ, dùng chung cho dòng chỉ mục và từ khoá."""

from __future__ import annotations

import re
import threading
import unicodedata
from typing import Protocol

#: Từ hỏi và hư từ: bỏ khỏi cả dòng chỉ mục lẫn từ khoá, nên hai bên vẫn khớp nhau.
VIETNAMESE_STOPWORDS = frozenset(
    "là gì nào ai đâu ở bao nhiêu thế sao như của và các những cho có được thì mà để với khi nếu về tại".split()
)


class WordSegmenter(Protocol):
    """Tách một đoạn chữ thành từ, từ ghép nối âm tiết bằng dấu ``_``."""

    name: str

    def segment(self, text: str) -> list[str]: ...


class UndertheseaSegmenter:
    """Tách từ ghép tiếng Việt bằng ``underthesea.word_tokenize``.

    Thư viện được nạp ở lần gọi đầu, nên nhập module này không tốn gì. Mô hình tách
    từ không cam kết an toàn khi nhiều luồng gọi cùng lúc, nên các lần gọi đi qua
    một khoá.
    """

    name = "underthesea"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._word_tokenize = None

    def segment(self, text: str) -> list[str]:
        with self._lock:
            if self._word_tokenize is None:
                from underthesea import word_tokenize

                self._word_tokenize = word_tokenize
            return self._word_tokenize(text, format="text").split()


class TextAnalyzer:
    """Biến chữ thành từ: âm tiết riêng lẻ cộng từ ghép.

    Âm tiết giữ cho từ khoá khớp được cả khi cách tách từ ghép hai bên khác nhau; từ
    ghép ("nghỉ_học", "tạm_thời") phân biệt "tạm thời" với "thời tiết", thứ âm tiết
    riêng lẻ không làm được.

    Không sửa lỗi gõ và không bung viết tắt: từ khoá do LLM viết lại đã đúng chính
    tả; tên viết tắt như "CNTT" nên được khai làm skos:altLabel trong dữ liệu.
    """

    _WORD = re.compile(r"\w+", re.UNICODE)
    #: Dấu câu cắt đoạn trước khi tách từ ghép, để "tại | Phòng" không thành "|_Phòng".
    _PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)

    def __init__(
        self,
        segmenter: WordSegmenter | None = None,
        stopwords: frozenset[str] = VIETNAMESE_STOPWORDS,
    ) -> None:
        self.segmenter = segmenter if segmenter is not None else UndertheseaSegmenter()
        self.stopwords = stopwords

    @property
    def name(self) -> str:
        """Định danh cách tách từ, ghi vào chỉ mục đã lưu để không nạp nhầm."""

        return f"syllables+{self.segmenter.name}"

    def normalize(self, text: str) -> str:
        return unicodedata.normalize("NFC", text).casefold()

    def syllables(self, text: str) -> list[str]:
        return [word for word in self._WORD.findall(self.normalize(text)) if word not in self.stopwords]

    def compounds(self, text: str) -> list[str]:
        """Từ ghép của đoạn chữ; bỏ từ ghép chỉ gồm từ hỏi như "bao_nhiêu"."""

        found: list[str] = []
        for chunk in self._PUNCTUATION.split(unicodedata.normalize("NFC", text)):
            if not chunk.strip():
                continue
            for word in self.segmenter.segment(chunk):
                word = word.casefold()
                parts = word.split("_")
                if len(parts) > 1 and not all(part in self.stopwords for part in parts):
                    found.append(word)
        return found

    def tokens(self, text: str) -> list[str]:
        return self.compounds(text) + self.syllables(text)

    def terms(self, text: str) -> list[str]:
        """Từ của một dòng, mỗi từ một lần.

        Dòng quan hệ thường lặp chữ ở hai đầu ("Nghỉ học tạm thời | có bước | Nghỉ
        học tạm thời - bước 1"). Đếm lặp thì dòng đó được tính điểm hai lần cho cùng
        một chữ và đè lên dòng tên chính; một dòng chỉ nên được hỏi là có chữ đó hay không.
        """

        return list(dict.fromkeys(self.tokens(text)))
