"""Tách chữ thành từ, dùng chung cho dòng chỉ mục và từ khoá."""

from __future__ import annotations

import re
import unicodedata

#: Từ hỏi và hư từ: bỏ ở cả dòng chỉ mục lẫn từ khoá, nên hai bên vẫn khớp nhau.
VIETNAMESE_STOPWORDS = frozenset(
    "là gì nào ai đâu ở bao nhiêu thế sao như của và các những cho có được thì mà để với khi nếu về tại".split()
)


class TextAnalyzer:
    """Chữ thành âm tiết: chuẩn hoá NFC, chữ thường, bỏ từ hỏi.

    Không tách từ ghép, không sửa lỗi gõ, không bung viết tắt; viết tắt khai làm tên gọi khác
    trong dữ liệu.
    """

    _WORD = re.compile(r"\w+", re.UNICODE)

    def __init__(self, stopwords: frozenset[str] = VIETNAMESE_STOPWORDS) -> None:
        self.stopwords = stopwords

    def terms(self, text: str) -> list[str]:
        """Các từ của một dòng, mỗi từ một lần: dòng lặp chữ không được cộng điểm hai lần."""

        words = self._WORD.findall(unicodedata.normalize("NFC", text).casefold())
        return list(dict.fromkeys(word for word in words if word not in self.stopwords))
