"""Chuẩn hóa source có kiểm soát trước tokenizer.

Chỉ bung các viết tắt có một nghĩa ổn định trong miền học vụ. Hàm này không
dò entity, không sửa từ gần đúng và không sinh IRI/SPARQL thay cho model.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_TONE_MARKS = "̣̀́̃̉"
_TONE_MOVE = re.compile(f"([oOuU])([{_TONE_MARKS}])([aeyAEY])")
_TONE_CLUSTERS = frozenset({("o", "a"), ("o", "e"), ("u", "y")})
_COHORT = re.compile(r"(?<!\w)(?:k|khoa)\s*(\d{2})(?!\w)", re.IGNORECASE)
_CREDITS = re.compile(
    r"(?<!\w)(\d+)\s*(?:tc|tin)(?!\w)",
    re.IGNORECASE,
)
_ABBREVIATIONS = {
    "bn": "bao nhiêu",
    "bnhiu": "bao nhiêu",
    "cnsh": "công nghệ sinh học",
    "cntt": "công nghệ thông tin",
    "cpa": "điểm trung bình tích luỹ",
    "ctsv": "công tác sinh viên",
    "dky": "đăng ký",
    "dkhp": "đăng ký học phần",
    "ds": "danh sách",
    "dtdh": "đào tạo đại học",
    "gdtq": "giáo dục tổng quát",
    "hb": "học bổng",
    "hbkk": "học bổng khuyến khích học tập",
    "hc": "học",
    "kq": "kết quả",
    "k": "không",
    "ko": "không",
    "lm": "làm",
    "mun": "muốn",
    "mún": "muốn",
    "nna": "ngôn ngữ Anh",
    "ntn": "như thế nào",
    "ntts": "nuôi trồng thuỷ sản",
    "nvqs": "nghĩa vụ quân sự",
    "qd": "quyết định",
    "sdt": "số điện thoại",
    "sv": "sinh viên",
    "tc": "tín chỉ",
    "tkb": "thời khoá biểu",
    "tn": "tốt nghiệp",
    "vb": "văn bản",
    "j": "gì",
    "r": "rồi",
    "s": "sao",
}
_ABBREVIATION = re.compile(
    r"(?<!\w)("
    + "|".join(
        sorted((re.escape(key) for key in _ABBREVIATIONS), key=len, reverse=True)
    )
    + r")(?!\w)",
    re.IGNORECASE,
)


def normalize_model_input(text: str) -> str:
    """Chuẩn hóa Unicode và bung whitelist viết tắt theo ranh giới token."""

    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)

    def move_tone(match: re.Match) -> str:
        first, tone, second = match.groups()
        if (first.lower(), second.lower()) in _TONE_CLUSTERS:
            return first + second + tone
        return match.group(0)

    normalized = _TONE_MOVE.sub(move_tone, normalized)
    normalized = unicodedata.normalize("NFC", normalized)
    normalized = _COHORT.sub(r"khoá \1", normalized)
    normalized = _CREDITS.sub(r"\1 tín chỉ", normalized)
    normalized = _ABBREVIATION.sub(
        lambda match: _ABBREVIATIONS[match.group(1).casefold()],
        normalized,
    )
    return _WHITESPACE.sub(" ", normalized).strip()
