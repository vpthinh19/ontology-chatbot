"""Vietnamese surface cleanup utilities used by the NER inference path.

The cleanup is *light* — diacritic preservation, URL/email removal, casual
abbreviation expansion, and word segmentation — chosen to keep the user's
phrasing intact while normalising the most common conversational artefacts.
Pre-compiled regexes avoid per-call compilation overhead in the chatbot
hot path.
"""

from __future__ import annotations

import re

from underthesea import text_normalize, word_tokenize

ABBREVIATION_MAP: dict[str, str] = {
    "ĐKHP": "đăng ký học phần", "KQHT": "kết quả học tập",
    "CTDT": "chương trình đào tạo", "ĐK": "đăng ký", "BL": "bảo lưu",
    "TN": "tốt nghiệp", "HP": "học phần", "SV": "sinh viên",
    "GV": "giảng viên", "CVHT": "cố vấn học tập",
    "PĐT": "phòng đào tạo", "PDT": "phòng đào tạo",
    "KHTC": "kế hoạch tài chính", "CTSV": "công tác sinh viên",
    "TKB": "thời khoá biểu", "HK": "học kỳ",
}

TEENCODE_MAP: dict[str, str] = {
    "ko": "không", "k": "không", "kh": "không", "hk": "không", "kg": "không",
    "dc": "được", "đc": "được", "dk": "được", "đk": "được",
    "vs": "với", "trc": "trước", "trog": "trong",
    "ntn": "như thế nào", "nth": "như thế nào", "j": "gì", "ji": "gì",
    "tks": "cảm ơn", "thanks": "cảm ơn",
}

_RE_URL = re.compile(r"(?:https?://|www\.)\S+")
_RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
_RE_REPEAT = re.compile(r"(.)\1{2,}")
_RE_WS = re.compile(r"\s+")


def _expand(words: list[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        if w in ABBREVIATION_MAP:
            out.extend(ABBREVIATION_MAP[w].split())
            continue
        u = w.upper()
        if u in ABBREVIATION_MAP:
            out.extend(ABBREVIATION_MAP[u].split())
            continue
        repl = TEENCODE_MAP.get(w.lower())
        if repl is not None:
            out.extend(repl.split())
        else:
            out.append(w)
    return out


def clean(text: str) -> str:
    """Apply normalisation, URL/email/emoji stripping, and slang expansion."""
    if not text:
        return ""
    text = text_normalize(text.strip())
    text = _RE_URL.sub(" ", text)
    text = _RE_EMAIL.sub(" ", text)
    text = _RE_REPEAT.sub(r"\1\1", text)
    text = " ".join(_expand(text.split()))
    return _RE_WS.sub(" ", text).strip()


def segment(text: str) -> list[str]:
    """Word-segment via underthesea, returning underscore-joined tokens."""
    out = word_tokenize(text, format="text")
    out = out if isinstance(out, str) else " ".join(out)
    return [t for t in out.split() if t]


def clean_and_segment(text: str) -> list[str]:
    return segment(clean(text))
