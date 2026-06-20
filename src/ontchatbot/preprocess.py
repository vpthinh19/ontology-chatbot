"""Tiền xử lý text TRƯỚC khi đưa vào model — pha "preprocess" của pipeline.

Nguyên tắc (DESIGN.md §2/§9): module này phải **"ngu"** — chỉ làm sạch ký tự, KHÔNG
trích xuất thực thể / dò intent / quét lexicon. Mọi việc *hiểu câu* dồn cho model. Không
word-segment (BARTpho nuốt raw syllable; runtime không kéo torch/underthesea). Hai nhóm việc:

* :func:`clean` — NFC + :func:`normalize_tone` + bung teencode/viết tắt → chuỗi sạch nạp model.
* :func:`normalize_tone` — nắn dấu thanh kiểu-cũ→mới (``thủy``→``thuỷ``) cho cụm oa/oe/uy: BARTpho
  tokenize ``thủy`` → ``<unk>``. Dùng cả ở :func:`clean` (source) lẫn `tree.to_model_json` (target).
* :func:`normalize_for_match` / :func:`is_url` — chuẩn hoá thấp (bỏ dấu, alnum) dùng
  chung cho `ontology` khi khớp alias.

Mọi hàm ở mức module; không trạng thái.
"""

from __future__ import annotations

import re
import unicodedata

# Domain acronyms — uppercase, multi-letter. Matched case-sensitively first
# (so ``HK`` does not catch a user typing ``hk`` for ``không``).
ABBREVIATION_MAP: dict[str, str] = {
    "ĐKHP": "đăng ký học phần", "DKHP": "đăng ký học phần",
    "ĐKMH": "đăng ký môn học", "DKMH": "đăng ký môn học",
    "KQHT": "kết quả học tập",
    "CTĐT": "chương trình đào tạo", "CTDT": "chương trình đào tạo",
    "CVHT": "cố vấn học tập", "TKB": "thời khoá biểu",
    "MH": "môn học", "TC": "tín chỉ", "BL": "bảo lưu",
    "GDTC": "giáo dục thể chất", "GDQP": "giáo dục quốc phòng",
    "TBC": "trung bình chung", "CPA": "điểm trung bình tích luỹ",
    "GPA": "điểm trung bình",
    "PĐT": "phòng đào tạo", "PDT": "phòng đào tạo",
    "KHTC": "kế hoạch tài chính", "CTSV": "công tác sinh viên",
    "VPT": "văn phòng trường", "ThS": "thạc sĩ", "PGS": "phó giáo sư",
    "TKNH": "tài khoản ngân hàng",
}


# Lower-case chat / teen-code spellings. Whole-token, case-insensitive.
# Single-character keys (``k`` → ``không``) only apply to whole-token matches,
# so alphanumeric IDs like ``k65`` are never broken.
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
    "cx": "cũng", "cg": "cũng", "ms": "mới",
    "r": "rồi", "oy": "rồi", "rui": "rồi",
    "h": "giờ", "jh": "giờ",
    "hc": "học", "hoc": "học", "hp": "học phí",
    "tn": "tốt nghiệp", "nganh": "ngành",
    "sv": "sinh viên", "gv": "giảng viên",
    "tcsv": "tín chỉ sinh viên", "tbnam": "trung bình năm",
    "tbhk": "trung bình học kỳ",
    "hk1": "học kỳ một", "hk2": "học kỳ hai",
    "ts": "tiến sĩ", "nh": "ngân hàng", "ck": "chuyển khoản",
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
    "đăn": "đăng",
    # NB: domain-entity surface forms (e.g. "cntt") deliberately do NOT live
    # here — they are ontology aliases owned by the graph lexicon. Teencode is
    # only for generic chat abbreviations; expanding "cntt" → "công nghệ thông
    # tin" would let longest-match swallow it into a fee label and break the
    # cohort×program intersection.
}


_RE_URL = re.compile(r"(?:https?://|www\.)\S+")
_RE_EMAIL = re.compile(r"\S+@\S+\.\S+")
_RE_REPEAT = re.compile(r"(.)\1{2,}")          # okkkk → okk
_RE_REPEAT_FULL = re.compile(r"(.)\1+")        # full collapse fallback
_RE_WS = re.compile(r"\s+")
_RE_LETTERS_DIGITS = re.compile(r"^([A-Za-zÀ-ỹđĐ]+)(\d.*)$")
_RE_NONALNUM = re.compile(r"[^\w\s]+")

# Multi-char keys used to peel a stuck acronym off a letter+digit token
# (``hpk65`` → ``hp k65``). Single-letter keys are excluded so ``k65`` survives.
_KNOWN_PREFIXES: frozenset[str] = frozenset(
    k.lower() for k in (*ABBREVIATION_MAP, *TEENCODE_MAP)
    if k.isalpha() and len(k) >= 2
)


def normalize(text: str) -> str:
    """NFC + whitespace collapse — the light path (no expansion)."""
    if not text:
        return ""
    return _RE_WS.sub(" ", unicodedata.normalize("NFC", text.strip()))


# Dấu thanh tổ hợp (NFD): huyền U+0300, sắc U+0301, ngã U+0303, hỏi U+0309, nặng U+0323.
_TONE_MARKS = "̣̀́̃̉"
_RE_TONE_MOVE = re.compile(f"([oOuU])([{_TONE_MARKS}])([aeyAEY])")
# Chỉ 3 cụm này khác nhau giữa "kiểu cũ" (dấu trên nguyên âm đầu) và "kiểu mới" (trên nguyên âm sau).
_TONE_CLUSTERS = frozenset({("o", "a"), ("o", "e"), ("u", "y")})


def normalize_tone(text: str) -> str:
    """Nắn dấu thanh **kiểu-cũ → kiểu-mới** cho cụm ``oa/oe/uy`` (vd ``thủy``→``thuỷ``, ``khóa``→``khoá``).

    BARTpho-syllable tokenize theo kiểu MỚI (dấu trên nguyên âm SAU): ``thủy`` (dấu trên ``u``) →
    ``<unk>``; ``thuỷ`` (dấu trên ``y``) → ``▁thu``+``ỷ``. Hàm chỉ DỜI dấu trong 3 cụm oa/oe/uy
    (chỗ hai kiểu khác nhau); ``của``/``mùa``/``tuần`` (cụm ua/uâ…) giữ NGUYÊN. Idempotent với dạng
    đã-mới. Khớp ontology vốn bỏ hết dấu (``normalize_for_match``) nên KHÔNG đổi kết quả khớp; đây
    thuần là để text vào tokenizer round-trip (97%→100%, kiểm 2026-06-19). Cũng làm hệ bền với việc
    người dùng gõ lẫn hai kiểu."""
    def _move(m: re.Match) -> str:
        v1, tone, v2 = m.group(1), m.group(2), m.group(3)
        return (v1 + v2 + tone) if (v1.lower(), v2.lower()) in _TONE_CLUSTERS else m.group(0)
    return unicodedata.normalize("NFC", _RE_TONE_MOVE.sub(_move, unicodedata.normalize("NFD", text)))


def clean(text: str) -> str:
    """Làm sạch input cho model: NFC → nắn dấu kiểu-mới → bỏ URL/email → bung teencode.

    Không word-segment — BARTpho tokenise raw syllable trực tiếp.
    """
    if not text:
        return ""
    text = normalize(text)
    text = normalize_tone(text)                    # thủy→thuỷ… cho tokenizer (đồng bộ với target)
    text = _RE_URL.sub(" ", text)
    text = _RE_EMAIL.sub(" ", text)
    text = _RE_REPEAT.sub(r"\1\1", text)
    text = _split_sticky_alnum(text)
    text = " ".join(_expand(text.split()))
    return _RE_WS.sub(" ", text).strip()


def normalize_for_match(text: str) -> str:
    """Diacritic-stripped, lowercase, alnum-only — fuzzy-index keys."""
    nfkd = unicodedata.normalize("NFD", text.lower())
    no_diac = "".join(c for c in nfkd if not unicodedata.combining(c))
    no_diac = no_diac.replace("đ", "d").replace("Đ", "d")
    return _RE_WS.sub(" ", _RE_NONALNUM.sub(" ", no_diac)).strip()


def is_url(s: object) -> bool:
    """True iff ``s`` is an ``http(s)://`` string."""
    return isinstance(s, str) and s.startswith(("http://", "https://"))


# Internal passes


def _split_sticky_alnum(text: str) -> str:
    """Peel a known acronym off a letter+digit token (``hpk65`` → ``hp k65``)."""
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
    """Map a token through acronym/teencode tables; pass through on miss.

    Fallback: a fully-collapsed form (``okkkk`` → ``ok``) is retried so user
    emphasis still resolves.
    """
    if tok in ABBREVIATION_MAP:
        return ABBREVIATION_MAP[tok].split()
    upper = tok.upper()
    if upper in ABBREVIATION_MAP:
        return ABBREVIATION_MAP[upper].split()
    lower = tok.lower()
    repl = TEENCODE_MAP.get(lower)
    if repl is not None:
        return repl.split()
    collapsed = _RE_REPEAT_FULL.sub(r"\1", lower)
    if collapsed != lower:
        repl = TEENCODE_MAP.get(collapsed)
        if repl is not None:
            return repl.split()
    return [tok]


def _expand(words: list[str]) -> list[str]:
    out: list[str] = []
    for w in words:
        out.extend(_expand_token(w))
    return out
