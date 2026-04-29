"""Vietnamese text preprocessing for PhoBERT pipeline.

All regex patterns are pre-compiled at module level for performance.
"""

import re

from underthesea import word_tokenize, text_normalize


# Teencode & abbreviation maps

TEENCODE_MAP = {
    "ko": "không", "k": "không", "hk": "không", "hem": "không", "kg": "không",
    "dc": "được", "đc": "được", "dk": "được", "đk": "được",
    "mk": "mình", "mik": "mình",
    "bn": "bạn", "bạ": "bạn",
    "cx": "cũng", "cg": "cũng",
    "vs": "với", "vói": "với",
    "trc": "trước", "trog": "trong",
    "ns": "nói", "nch": "nói chuyện",
    "ạ": "", "a": "anh", "e": "em",
    "r": "rồi", "oy": "rồi",
    "đag": "đang", "dg": "đang",
    "dt": "điện thoại", "sdt": "số điện thoại",
    "gd": "gia đình", "sv": "sinh viên",
    "gv": "giảng viên", "hp": "học phần",
    "nv": "nhân viên", "tn": "tốt nghiệp",
    "hsg": "học sinh giỏi", "đh": "đại học",
    "ths": "thạc sĩ", "ts": "tiến sĩ",
    "pdt": "phòng đào tạo", "qldt": "quản lý đào tạo",
    "khtc": "kế hoạch tài chính",
    "ctsv": "công tác sinh viên",
    "ntn": "như thế nào", "nth": "như thế nào",
    "sao": "sao", "lm": "làm", "lam": "làm",
    "j": "gì", "ji": "gì", "g": "gì",
    "đi": "đi", "di": "đi",
    "tks": "cảm ơn", "thenks": "cảm ơn", "thanks": "cảm ơn",
    "pls": "xin vui lòng", "plz": "xin vui lòng",
    "ok": "được", "okie": "được", "oke": "được",
    "bt": "bình thường", "bth": "bình thường",
    "vd": "ví dụ", "td": "tương đương",
    "tg": "thời gian", "đk": "điều kiện",
    "nt": "nhắn tin", "mess": "nhắn tin",
    "fb": "facebook", "zl": "zalo",
    "ae": "anh em", "mn": "mọi người",
    "ad": "admin", "mod": "người quản lý",
}

ABBREVIATION_MAP = {
    "ĐKHP": "đăng ký học phần",
    "KQHT": "kết quả học tập",
    "CTDT": "chương trình đào tạo",
    "ĐK": "đăng ký",
    "BL": "bảo lưu",
    "TN": "tốt nghiệp",
    "HP": "học phần",
    "SV": "sinh viên",
    "GV": "giảng viên",
    "CVHT": "cố vấn học tập",
    "PDT": "phòng đào tạo",
    "KHTC": "kế hoạch tài chính",
    "CTSV": "công tác sinh viên",
    "TKB": "thời khóa biểu",
    "HK": "học kỳ",
}


# Pre-compiled regex patterns

_RE_URL_HTTP = re.compile(r"https?://\S+")
_RE_URL_WWW = re.compile(r"www\.\S+")
_RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
_RE_SPECIAL_CHARS = re.compile(r"[^\w\s.,?!;:'\"\-/]")
_RE_REPEATED_CHARS = re.compile(r"(.)\1{2,}")
_RE_EMOJI = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251"
    "]+",
    flags=re.UNICODE,
)
_RE_TEXT_EMOJI = re.compile(r"[:;][-']?[)(DPp/\\|]")
_RE_WHITESPACE = re.compile(r"\s+")


# Cleaning helpers

def _remove_urls(text: str) -> str:
    text = _RE_URL_HTTP.sub(" ", text)
    text = _RE_URL_WWW.sub(" ", text)
    return text


def _remove_emails(text: str) -> str:
    return _RE_EMAIL.sub(" ", text)


def _remove_special_chars(text: str) -> str:
    return _RE_SPECIAL_CHARS.sub(" ", text)


def _normalize_teencode(text: str) -> str:
    words = text.split()
    out: list[str] = []
    for word in words:
        if word in ABBREVIATION_MAP:
            out.append(ABBREVIATION_MAP[word])
            continue
        upper = word.upper()
        if upper in ABBREVIATION_MAP:
            out.append(ABBREVIATION_MAP[upper])
            continue
        lower = word.lower()
        replacement = TEENCODE_MAP.get(lower)
        if replacement:
            out.append(replacement)
        else:
            out.append(word)
    return " ".join(out)


def _normalize_repeated_chars(text: str) -> str:
    return _RE_REPEATED_CHARS.sub(r"\1\1", text)


def _remove_emojis(text: str) -> str:
    text = _RE_EMOJI.sub(" ", text)
    text = _RE_TEXT_EMOJI.sub(" ", text)
    return text


# Public API

def preprocess_text(text: str, word_segmentation: bool = True) -> str:
    """Clean and segment Vietnamese text for PhoBERT."""
    text = text.strip()
    if not text:
        return ""

    text = text_normalize(text)
    text = _remove_urls(text)
    text = _remove_emails(text)
    text = _remove_emojis(text)
    text = _remove_special_chars(text)
    text = _normalize_repeated_chars(text)
    text = _normalize_teencode(text)
    text = _RE_WHITESPACE.sub(" ", text).strip()

    if word_segmentation:
        tokens = word_tokenize(text, format="text")
        text = " ".join(tokens) if isinstance(tokens, list) else tokens

    return text

def preprocess_batch(texts: list[str], word_segmentation: bool = True) -> list[str]:
    """Clean and segment a batch of Vietnamese texts for PhoBERT."""
    return [preprocess_text(text, word_segmentation) for text in texts]
