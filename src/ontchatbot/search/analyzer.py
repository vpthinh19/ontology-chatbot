"""Tách chữ thành từ, dùng chung cho dòng chỉ mục và từ khoá."""

from __future__ import annotations

import re
import unicodedata

#: Từ hỏi và hư từ: bỏ khỏi cả dòng chỉ mục lẫn từ khoá, nên hai bên vẫn khớp nhau.
VIETNAMESE_STOPWORDS = frozenset(
    "là gì nào ai đâu ở bao nhiêu thế sao như của và các những cho có được thì mà để với khi nếu về tại".split()
)


class TextAnalyzer:
    """Chuẩn hoá Unicode, viết thường, tách theo âm tiết, bỏ từ hỏi.

    Không sửa lỗi gõ và không bung viết tắt: từ khoá do LLM viết lại đã đúng chính
    tả; tên viết tắt như "CNTT" nên được khai làm skos:altLabel trong dữ liệu.
    """

    _WORD = re.compile(r"\w+", re.UNICODE)

    def __init__(self, stopwords: frozenset[str] = VIETNAMESE_STOPWORDS) -> None:
        self.stopwords = stopwords

    def normalize(self, text: str) -> str:
        return unicodedata.normalize("NFC", text).casefold()

    def tokens(self, text: str) -> list[str]:
        return [word for word in self._WORD.findall(self.normalize(text)) if word not in self.stopwords]

    def terms(self, text: str) -> list[str]:
        """Từ của một dòng, mỗi từ một lần.

        Dòng quan hệ thường lặp chữ ở hai đầu ("Nghỉ học tạm thời | có bước | Nghỉ
        học tạm thời - bước 1"). Đếm lặp thì dòng đó được cộng điểm hai lần cho cùng
        một chữ và đè lên dòng tên chính; một dòng chỉ nên được hỏi là có chữ đó hay không.
        """

        return list(dict.fromkeys(self.tokens(text)))
