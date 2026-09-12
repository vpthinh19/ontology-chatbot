"""Tách chữ thành từ, dùng chung cho dòng chỉ mục và từ khoá."""

from __future__ import annotations

import re
import unicodedata

#: Từ hỏi và hư từ: bỏ khỏi cả dòng chỉ mục lẫn từ khoá, nên hai bên vẫn khớp nhau.
VIETNAMESE_STOPWORDS = frozenset(
    "là gì nào ai đâu ở bao nhiêu thế sao như của và các những cho có được thì mà để với khi nếu về tại".split()
)


class TextAnalyzer:
    """Biến chữ thành từ: âm tiết, bỏ từ hỏi.

    Không tách từ ghép: đo trên 51 câu hỏi thật thì tách hay không cho kết quả như
    nhau (44 so với 45 câu tìm đúng, và tách từ ghép còn xếp mục đúng lên đầu ít
    hơn), trong khi thư viện tách từ chiếm gần hết thời gian dựng chỉ mục và gần
    30 MB phụ thuộc.

    Không sửa lỗi gõ và không bung viết tắt: từ khoá do mô hình viết lại đã đúng
    chính tả; tên viết tắt như "CNTT" nên được khai làm tên gọi phụ trong dữ liệu.
    """

    _WORD = re.compile(r"\w+", re.UNICODE)

    def __init__(self, stopwords: frozenset[str] = VIETNAMESE_STOPWORDS) -> None:
        self.stopwords = stopwords

    @property
    def name(self) -> str:
        """Định danh cách tách từ, ghi vào chỉ mục đã lưu để không nạp nhầm."""

        return "syllables"

    def normalize(self, text: str) -> str:
        return unicodedata.normalize("NFC", text).casefold()

    def syllables(self, text: str) -> list[str]:
        return [word for word in self._WORD.findall(self.normalize(text)) if word not in self.stopwords]

    def tokens(self, text: str) -> list[str]:
        return self.syllables(text)

    def terms(self, text: str) -> list[str]:
        """Từ của một dòng, mỗi từ một lần.

        Dòng quan hệ hay lặp chữ ở hai đầu. Đếm lặp thì dòng đó được tính điểm hai
        lần cho cùng một chữ và đè lên dòng tên chính; một dòng chỉ nên được hỏi là
        có chữ đó hay không.
        """

        return list(dict.fromkeys(self.tokens(text)))
