"""Vietnamese text preprocessing — single source of truth.

Owns: light normalisation (dataset path), full cleanup (inference path),
word segmentation, diacritic stripping, URL detection, fuzzy-match
normalisation. Singleton via :meth:`Preprocessor.get`.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from functools import lru_cache

from underthesea import text_normalize, word_tokenize

log = logging.getLogger(__name__)


# Vietnamese vowel groups paired with their unaccented Latin equivalent.
# Used by :meth:`Preprocessor.strip_diacritics`. Kept module-private because
# nothing outside the preprocessor should be doing diacritic surgery
# manually — the greeting heuristic and the matcher both go through the
# preprocessor.
_GROUPS: tuple[tuple[str, str], ...] = (
    ("àáảãạâầấẩẫậăằắẳẵặ", "a"),
    ("èéẻẽẹêềếểễệ", "e"),
    ("ìíỉĩị", "i"),
    ("òóỏõọôồốổỗộơờớởỡợ", "o"),
    ("ùúủũụưừứửữự", "u"),
    ("ỳýỷỹỵ", "y"),
    ("đ", "d"),
)
_VOWELS = "".join(g for g, _ in _GROUPS)
_PLAIN = "".join(p * len(g) for g, p in _GROUPS)
_DIACRITIC_TABLE = str.maketrans(_VOWELS + _VOWELS.upper(),
                                 _PLAIN + _PLAIN.upper())


# Domain acronyms — uppercase, multi-letter. Matched case-sensitively first
# (so ``HK`` does not catch a user typing ``hk`` for ``không``) and then
# after upper-casing the token.
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
# Single-character keys (``k`` → ``không``) only apply to whole-token
# matches, so alphanumeric IDs like ``k65`` are never broken.
TEENCODE_MAP: dict[str, str] = {
    "ko": "không", "kh": "không", "khong": "không",
    "hk": "không", "hong": "không", "kg": "không", "k": "không",
    "dc": "được", "đc": "được", "dk": "được", "đk": "được", "duoc": "được",
    "j": "gì", "ji": "gì", "g": "gì",
    "z": "vậy", "zay": "vậy", "v": "vậy",
    "ntn": "như thế nào", "nth": "như thế nào", "ntnao": "như thế nào",
    "thnao": "thế nào",
    "bgio": "bao giờ", "bjo": "bao giờ", "bg": "bao giờ",
    "khinao": "khi nào", "kn": "khi nào",
    "mk": "mình", "mik": "mình", "m": "mình",
    "bn": "bạn", "bạ": "bạn",
    "ad": "admin", "mod": "quản trị",
    "mn": "mọi người", "ae": "anh em",
    "lm": "làm", "lam": "làm",
    "đg": "đang", "dg": "đang", "dag": "đang", "đag": "đang",
    "trc": "trước", "trog": "trong",
    "ngta": "người ta", "ng": "người",
    "vs": "với", "voi": "với",
    "cx": "cũng", "cg": "cũng",
    "ms": "mới",
    "r": "rồi", "oy": "rồi", "rui": "rồi",
    "h": "giờ", "jh": "giờ",
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
    "tks": "cảm ơn", "thanks": "cảm ơn", "thank": "cảm ơn",
    "ty": "cảm ơn", "tysm": "cảm ơn rất nhiều",
    "pls": "xin vui lòng", "plz": "xin vui lòng",
    "ok": "được", "okie": "được", "oke": "được", "okela": "được",
    "thik": "thích", "thij": "thích", "lik": "thích",
    "iu": "yêu",
    "bik": "biết", "bjk": "biết", "bjt": "biết",
    "fai": "phải", "phai": "phải",
    "khgo": "không có", "kgcg": "không có gì",
    "đăn": "đăng", "đag": "đang",
}


_RE_URL = re.compile(r"(?:https?://|www\.)\S+")
_RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
_RE_REPEAT = re.compile(r"(.)\1{2,}")
# Used as a fallback when token-level lookup misses: collapse consecutive
# duplicates (2+) to a single char so user emphasis like ``okkkk`` still
# matches teen-code ``ok``.
_RE_REPEAT_FULL = re.compile(r"(.)\1+")
_RE_WS = re.compile(r"\s+")
_RE_LETTERS_DIGITS = re.compile(r"^([A-Za-zÀ-ỹđĐ]+)(\d.*)$")
_RE_NONALNUM = re.compile(r"[^\w\s]+")


class Preprocessor:
    """Vietnamese chat-input cleaner + segmenter; singleton via ``get()``."""

    def __init__(self,
                 abbrev_map: dict[str, str] | None = None,
                 teencode_map: dict[str, str] | None = None) -> None:
        self._abbrev = dict(abbrev_map if abbrev_map is not None else ABBREVIATION_MAP)
        self._teencode = dict(teencode_map if teencode_map is not None else TEENCODE_MAP)
        self._known_prefixes = self._compute_prefixes()
        log.debug("[Preprocessor] init abbrev=%d teencode=%d",
                  len(self._abbrev), len(self._teencode))

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Preprocessor":
        return cls()

    # Public API

    def normalize(self, text: str) -> str:
        """NFC + underthesea ``text_normalize`` — dataset path (no expansion)."""
        if not text:
            return ""
        return text_normalize(unicodedata.normalize("NFC", text.strip()))

    def clean(self, text: str) -> str:
        """Full cleanup chain for the NER inference path."""
        if not text:
            return ""
        text = self.normalize(text)
        text = _RE_URL.sub(" ", text)
        text = _RE_EMAIL.sub(" ", text)
        text = _RE_REPEAT.sub(r"\1\1", text)
        text = self._split_sticky_alnum(text)
        text = " ".join(self._expand(text.split()))
        return _RE_WS.sub(" ", text).strip()

    @staticmethod
    def segment(text: str) -> list[str]:
        """Word-segment via underthesea, returning underscore-joined tokens."""
        out = word_tokenize(text, format="text")
        out = out if isinstance(out, str) else " ".join(out)
        return [t for t in out.split() if t]

    def clean_and_segment(self, text: str) -> list[str]:
        return self.segment(self.clean(text))

    @staticmethod
    def strip_diacritics(s: str) -> str:
        """Remove Vietnamese tone marks (``cảm ơn`` → ``cam on``)."""
        return s.translate(_DIACRITIC_TABLE)

    @staticmethod
    def normalize_for_match(text: str) -> str:
        """Diacritic-stripped, lowercase, alnum-only — keys for the fuzzy index."""
        nfkd = unicodedata.normalize("NFD", text.lower())
        no_diac = "".join(c for c in nfkd if not unicodedata.combining(c))
        no_diac = no_diac.replace("đ", "d").replace("Đ", "d")
        return _RE_WS.sub(" ", _RE_NONALNUM.sub(" ", no_diac)).strip()

    @staticmethod
    def is_url(s: object) -> bool:
        """True iff ``s`` is a string starting with ``http://`` or ``https://``."""
        return isinstance(s, str) and s.startswith(("http://", "https://"))

    # Internal passes

    def _compute_prefixes(self) -> set[str]:
        """Lower-cased multi-char keys from both maps — used to detect sticky
        prefixes like ``hp`` glued to ``k65`` so we can split *only* there.

        Single-letter teen-code keys (``k`` → ``không``) are excluded so
        one-letter+digits identifiers (``k65``, ``x99``) are never broken.
        """
        out: set[str] = set()
        for k in self._abbrev:
            if k.isalpha() and len(k) >= 2:
                out.add(k.lower())
        for k in self._teencode:
            if k.isalpha() and len(k) >= 2:
                out.add(k.lower())
        return out

    def _split_sticky_alnum(self, text: str) -> str:
        """Peel a known acronym off a letter+digit token (``hpk65`` → ``hp k65``).

        A token is split only when its letter prefix begins with a known
        multi-character abbreviation — so ``k65`` (whose ``k`` is a teen-code
        single-letter key) survives unsplit while ``hpk65`` correctly peels
        ``hp`` off.
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
            split_at = next(
                (L for L in range(len(letters) - 1, 1, -1)
                 if letters[:L].lower() in self._known_prefixes),
                None,
            )
            if split_at is None:
                out.append(tok)
            else:
                out.append(letters[:split_at])
                out.append(letters[split_at:] + rest)
        return " ".join(out)

    def _expand_token(self, tok: str) -> list[str]:
        """Look the token up in both maps; substitute or pass through.

        Fallback: if a direct lookup misses, also try the fully-collapsed
        form (consecutive duplicates squashed to one char) so user emphasis
        like ``okkkk`` still resolves to teen-code ``ok``.
        """
        if tok in self._abbrev:
            return self._abbrev[tok].split()
        upper = tok.upper()
        if upper in self._abbrev:
            return self._abbrev[upper].split()
        lower = tok.lower()
        repl = self._teencode.get(lower)
        if repl is not None:
            return repl.split()
        collapsed = _RE_REPEAT_FULL.sub(r"\1", lower)
        if collapsed != lower:
            repl = self._teencode.get(collapsed)
            if repl is not None:
                return repl.split()
        return [tok]

    def _expand(self, words: list[str]) -> list[str]:
        out: list[str] = []
        for w in words:
            out.extend(self._expand_token(w))
        return out
