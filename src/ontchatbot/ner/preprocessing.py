"""Vietnamese surface cleanup utilities used by the NER inference path.

The cleanup is *light* but broad: it preserves the user's phrasing while
expanding the abbreviation forms and teen-code spellings that dominate
Vietnamese chat traffic. The pipeline is composed of small, deterministic
sub-passes that can be invoked independently for unit testing:

    1. Unicode NFC normalisation + ``underthesea.text_normalize``
    2. URL / email stripping
    3. Repeated-character collapse (``saooooo`` → ``saoo``)
    4. Sticky alphanumeric splitting (``hpk65`` → ``hp k65``) so domain
       acronyms re-attach to a separate token where teen-code lookup applies
    5. Whole-token expansion against :data:`ABBREVIATION_MAP`
       (case-sensitive + uppercase fallback) and :data:`TEENCODE_MAP`
       (case-insensitive)
    6. Whitespace collapse

Word segmentation is exposed as a separate function so callers can decide
when to incur the underthesea cost.
"""

from __future__ import annotations

import re
import unicodedata

from underthesea import text_normalize, word_tokenize


# Domain acronyms — uppercase, multi-letter. The keys are matched both
# case-sensitively (so ``HK`` does not catch the user typing ``hk`` for
# ``không``) and after upper-casing the input token.
ABBREVIATION_MAP: dict[str, str] = {
    "ĐKHP": "đăng ký học phần",
    "DKHP": "đăng ký học phần",
    "ĐKMH": "đăng ký môn học",
    "DKMH": "đăng ký môn học",
    "KQHT": "kết quả học tập",
    "CTĐT": "chương trình đào tạo",
    "CTDT": "chương trình đào tạo",
    "CVHT": "cố vấn học tập",
    "TKB": "thời khoá biểu",
    "MH": "môn học",
    "TC": "tín chỉ",
    "BL": "bảo lưu",
    "GDTC": "giáo dục thể chất",
    "GDQP": "giáo dục quốc phòng",
    "TBC": "trung bình chung",
    "CPA": "điểm trung bình tích luỹ",
    "GPA": "điểm trung bình",
    "PĐT": "phòng đào tạo",
    "PDT": "phòng đào tạo",
    "KHTC": "kế hoạch tài chính",
    "CTSV": "công tác sinh viên",
    "VPT": "văn phòng trường",
    "ThS": "thạc sĩ",
    "PGS": "phó giáo sư",
    "TKNH": "tài khoản ngân hàng",
}


# Lower-case chat / teen-code spellings. Whole-token, case-insensitive.
# Single-character keys (``k`` → ``không``) only apply to whole-token matches,
# so alphanumeric IDs like ``k65`` are never broken.
TEENCODE_MAP: dict[str, str] = {
    # negation / agreement
    "ko": "không", "kh": "không", "khong": "không",
    "hk": "không", "hong": "không", "kg": "không", "k": "không",
    # got / can
    "dc": "được", "đc": "được", "dk": "được", "đk": "được",
    "duoc": "được",
    # interrogatives
    "j": "gì", "ji": "gì", "g": "gì",
    "z": "vậy", "zay": "vậy", "v": "vậy",
    "ntn": "như thế nào", "nth": "như thế nào", "ntnao": "như thế nào",
    "thnao": "thế nào",
    "bgio": "bao giờ", "bjo": "bao giờ", "bg": "bao giờ",
    "khinao": "khi nào", "kn": "khi nào",
    # pronouns / fillers
    "mk": "mình", "mik": "mình", "m": "mình",
    "bn": "bạn", "bạ": "bạn",
    "ad": "admin", "mod": "quản trị",
    "mn": "mọi người", "ae": "anh em",
    # very common verbs / particles
    "lm": "làm", "lam": "làm",
    "đg": "đang", "dg": "đang", "dag": "đang", "đag": "đang",
    "trc": "trước", "trog": "trong",
    "ngta": "người ta", "ng": "người",
    "vs": "với", "voi": "với",
    "cx": "cũng", "cg": "cũng",
    "ms": "mới",
    "r": "rồi", "oy": "rồi", "rui": "rồi",
    "h": "giờ", "jh": "giờ",
    # academic chat shorthand (single-token whole match → safe with k65/k67)
    "hc": "học", "hoc": "học",
    "hp": "học phí",
    "tn": "tốt nghiệp",
    "nganh": "ngành",
    "sv": "sinh viên",
    "gv": "giảng viên",
    "tcsv": "tín chỉ sinh viên",
    "tbnam": "trung bình năm",
    "tbhk": "trung bình học kỳ",
    "hk1": "học kỳ một",
    "hk2": "học kỳ hai",
    "ts": "tiến sĩ",
    "nh": "ngân hàng",
    "ck": "chuyển khoản",
    "qr": "qr code",
    # gratitude / greetings
    "tks": "cảm ơn", "thanks": "cảm ơn", "thank": "cảm ơn",
    "ty": "cảm ơn", "tysm": "cảm ơn rất nhiều",
    "pls": "xin vui lòng", "plz": "xin vui lòng",
    "ok": "được", "okie": "được", "oke": "được", "okela": "được",
    # affect
    "thik": "thích", "thij": "thích", "lik": "thích",
    "iu": "yêu",
    "bik": "biết", "bjk": "biết", "bjt": "biết",
    "fai": "phải", "phai": "phải",
    "khgo": "không có", "kgcg": "không có gì",
    # filler interjections
    "haha": "", "hihi": "", "hehe": "", "huhu": "",
    "kkk": "", "kk": "", "uk": "", "uhm": "", "uhmm": "",
}


# Pre-compiled regexes
_RE_URL = re.compile(r"(?:https?://|www\.)\S+")
_RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
_RE_REPEAT = re.compile(r"(.)\1{2,}")
_RE_WS = re.compile(r"\s+")
_RE_LETTERS_DIGITS = re.compile(r"^([A-Za-zÀ-ỹđĐ]+)(\d.*)$")


def _known_alpha_prefixes() -> set[str]:
    """Lower-cased multi-character keys from both expansion maps.

    Single-letter teen-code keys (``k`` → ``không``) are deliberately
    excluded so that one-letter+digits identifiers (``k65``, ``x99``) are
    never split.
    """
    out: set[str] = set()
    for k in ABBREVIATION_MAP:
        if k.isalpha() and len(k) >= 2:
            out.add(k.lower())
    for k in TEENCODE_MAP:
        if k.isalpha() and len(k) >= 2:
            out.add(k.lower())
    return out


_KNOWN_PREFIXES: set[str] = _known_alpha_prefixes()


def _split_sticky_alnum(text: str) -> str:
    """Peel a known acronym off a letter+digit token (``hpk65`` → ``hp k65``).

    A token is only split when:

    * it begins with two or more letters followed by digits,
    * **and** a known multi-character prefix occurs strictly inside the
      letter run (the *interior-prefix* case, e.g. ``hp`` inside ``hpk``).

    Plain ``hp65`` (entire letter run is a known prefix) and pure IDs such
    as ``k65`` are left untouched: the entire token is later looked up as a
    whole — preserving the alphanumeric identifier.
    """
    out: list[str] = []
    for tok in text.split():
        m = _RE_LETTERS_DIGITS.match(tok)
        if not m:
            out.append(tok)
            continue
        letters, rest = m.group(1), m.group(2)
        if len(letters) < 3:
            out.append(tok)
            continue
        # Try the longest interior prefix first.
        split_at = next(
            (L for L in range(len(letters) - 1, 1, -1)
             if letters[:L].lower() in _KNOWN_PREFIXES),
            None,
        )
        if split_at is None:
            out.append(tok)
        else:
            out.append(letters[:split_at])
            out.append(letters[split_at:] + rest)
    return " ".join(out)


def _expand_token(tok: str) -> list[str]:
    """Look the token up in both maps; return the substituted words or ``[tok]``."""
    if tok in ABBREVIATION_MAP:
        return ABBREVIATION_MAP[tok].split()
    upper = tok.upper()
    if upper in ABBREVIATION_MAP:
        return ABBREVIATION_MAP[upper].split()
    repl = TEENCODE_MAP.get(tok.lower())
    if repl is not None:
        return repl.split()
    return [tok]


def _expand(words: list[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        out.extend(_expand_token(w))
    return out


def normalize_unicode(text: str) -> str:
    """NFC-normalise + apply underthesea's tone-mark cleanup."""
    if not text:
        return ""
    return text_normalize(unicodedata.normalize("NFC", text.strip()))


def clean(text: str) -> str:
    """Apply the full cleanup chain in canonical order."""
    if not text:
        return ""
    text = normalize_unicode(text)
    text = _RE_URL.sub(" ", text)
    text = _RE_EMAIL.sub(" ", text)
    text = _RE_REPEAT.sub(r"\1\1", text)
    text = _split_sticky_alnum(text)
    text = " ".join(_expand(text.split()))
    return _RE_WS.sub(" ", text).strip()


def segment(text: str) -> list[str]:
    """Word-segment via underthesea, returning underscore-joined tokens."""
    out = word_tokenize(text, format="text")
    out = out if isinstance(out, str) else " ".join(out)
    return [t for t in out.split() if t]


def clean_and_segment(text: str) -> list[str]:
    return segment(clean(text))
