"""Surface-form templates and noise functions for synthetic NER data.

The dataset is built by combining (i) a sentence template with one or more
``{ENT_<TAG>}`` placeholders, and (ii) a surface form for each placeholder
sampled from the ontology (canonical name + every ``hasAlias``). Templates are
deliberately diverse — declarative, interrogative, fragmentary, multi-entity,
out-of-domain — so the trained model generalises to the long tail of real
academic-procedure queries.

Noise functions inject realistic Vietnamese chat distortions: diacritic loss,
teencode, repeated characters, missing punctuation, and casing perturbations.
"""

from __future__ import annotations

import random
import re
import unicodedata


# Per-tag question/statement scaffolds. ``{E}`` marks the entity slot.
TEMPLATES: dict[str, list[str]] = {
    "QuyTrinhHocVu": [
        "{E} làm thế nào ạ ?", "{E} ra sao ?", "cho em hỏi {E} với", "em muốn hỏi về {E}",
        "{E} thì thực hiện như thế nào", "quy trình {E} là gì ?", "{E} cần làm gì ?",
        "ai phụ trách {E} vậy ?", "tài liệu cho {E} ở đâu", "thầy cô ơi {E} có khó không",
        "{E} có thời hạn không", "muốn {E} thì phải làm sao", "hướng dẫn {E} chi tiết",
        "{E} nộp ở đâu", "anh chị ơi {E} cần giấy tờ gì", "em mới năm 2 muốn {E}",
        "{E} liên hệ phòng nào", "{E} mất bao lâu", "{E} có mất phí không", "{E} ạ",
        "{E} đăng ký kiểu gì", "trường mình {E} thế nào", "{E} có được không",
        "có ai biết {E} không", "{E} đợt này còn kịp không", "{E} thủ tục ra sao",
    ],
    "PhongBanHanhChinh": [
        "cho mình xin số {E}", "{E} ở đâu ?", "liên hệ {E} sao ạ", "địa chỉ {E} là gì",
        "{E} làm việc giờ nào", "email {E} là gì", "{E} có website không",
        "trưởng phòng {E} là ai", "muốn gặp {E} thì sao", "{E} số điện thoại bao nhiêu",
        "phòng {E} ở tầng mấy", "{E} đi cổng nào", "{E} thứ bảy có làm không",
        "ai phụ trách bên {E}", "{E} hỗ trợ những gì", "em cần gặp {E}",
    ],
    "TaiLieuBieuMau": [
        "cho em xin {E}", "{E} tải ở đâu", "link {E} với ạ", "em cần file {E}",
        "{E} mẫu mới nhất", "biểu mẫu {E} ở đâu", "{E} điền sao cho đúng",
        "có {E} không ạ", "thầy cô gửi em {E} với", "{E} nộp ở đâu",
        "{E} có sẵn online không", "{E} có cần chữ ký không",
    ],
    "DinhMucHocPhi": [
        "{E} bao nhiêu", "{E} 1 tín chỉ giá nhiêu", "học phí {E} sao ạ",
        "{E} đóng bao nhiêu", "ngành em {E} là bao nhiêu", "{E} năm nay tăng không",
        "{E} có giảm cho hộ nghèo không", "cho hỏi {E}", "{E} thế nào",
        "{E} áp dụng cho ngành nào", "{E} căn cứ quyết định nào",
    ],
    "PhuongThucThanhToan": [
        "đóng học phí qua {E} được không", "{E} có hỗ trợ không", "muốn dùng {E}",
        "trường mình chấp nhận {E} chứ", "{E} thế nào", "có thể trả bằng {E}",
        "{E} có phí không",
    ],
}

# Sentence frames that combine TWO entities of (potentially) different classes.
# ``{E1}`` and ``{E2}`` each carry their own tag.
MULTI_TEMPLATES: list[str] = [
    "{E1} thì sao còn {E2} thì sao",
    "cho hỏi {E1} với cả {E2}",
    "{E1} như nào , {E2} nữa",
    "{E1} và {E2} có khác nhau không",
    "em cần {E1} và {E2}",
    "{E1} liên hệ ai , còn {E2} liên hệ ai",
    "{E1} ạ , thêm {E2} luôn nhé",
    "vừa {E1} vừa {E2} được không",
]

# Greetings & closings (no entity).
GREETINGS: list[str] = [
    "xin chào ạ", "chào thầy cô", "hello ạ", "hi mọi người", "chào shop",
    "em chào ạ", "cảm ơn nhiều", "thanks nhé", "tks ạ", "tạm biệt",
    "bye bye", "goodbye", "hẹn gặp lại", "chúc một ngày tốt lành",
    "ok cảm ơn", "dạ vâng cảm ơn", "ờ chào", "alo", "có ai không ạ",
    "em xin phép hỏi", "chào buổi sáng", "chào buổi tối",
]

# Out-of-domain: questions unrelated to academic procedures.
OUT_OF_DOMAIN: list[str] = [
    "thời tiết hôm nay thế nào", "có món gì ngon ở Nha Trang không",
    "trận bóng tối qua ai thắng", "kể chuyện cười cho em nghe",
    "hôm nay là ngày bao nhiêu", "địa chỉ wifi sinh viên",
    "đồng phục trường mua ở đâu", "ký túc xá có còn chỗ không",
    "câu lạc bộ tiếng anh sinh hoạt khi nào", "quán cà phê gần trường",
    "xe bus tuyến nào đến trường", "thư viện mở cửa lúc mấy giờ",
    "có chương trình trao đổi sinh viên không", "giải bóng đá khoa bao giờ",
    "bãi giữ xe sinh viên ở đâu", "trường có dịch vụ in ấn không",
    "wifi trường mật khẩu là gì", "hôm nay ăn gì",
    "bạn có biết yêu là gì không", "ai là hiệu trưởng đầu tiên",
    "lịch sử thành lập trường", "tôi muốn đặt vé máy bay",
    "mai mưa không nhỉ", "ngày mai có lễ hội gì",
]


# Surface-level noise

_VOWELS_DIACRITIC = (
    "àáảãạâầấẩẫậăằắẳẵặ"
    "èéẻẽẹêềếểễệ"
    "ìíỉĩị"
    "òóỏõọôồốổỗộơờớởỡợ"
    "ùúủũụưừứửữự"
    "ỳýỷỹỵ"
    "đ"
)
_VOWELS_PLAIN = (
    "aaaaaaaaaaaaaaaaa"
    "eeeeeeeeeee"
    "iiiii"
    "ooooooooooooooooo"
    "uuuuuuuuuuu"
    "yyyyy"
    "d"
)
_DIACRITIC_TABLE = str.maketrans(_VOWELS_DIACRITIC + _VOWELS_DIACRITIC.upper(),
                                 _VOWELS_PLAIN + _VOWELS_PLAIN.upper())


def strip_diacritics(s: str) -> str:
    return s.translate(_DIACRITIC_TABLE)


def lowercase(s: str) -> str:
    return s.lower()


def drop_punct(s: str) -> str:
    return re.sub(r"\s+([?,.!:;])", r"\1", s).rstrip("?.!,;:")


def repeat_chars(s: str, rng: random.Random) -> str:
    """Stretch a random vowel: 'sao' -> 'saoo'."""
    if len(s) < 4:
        return s
    i = rng.randrange(len(s))
    if s[i] in "aeiouAEIOU":
        return s[:i + 1] + s[i] + s[i:]
    return s


_NOISE_FNS = [strip_diacritics, lowercase, drop_punct, repeat_chars]


def perturb(text: str, rng: random.Random, p: float = 0.35) -> str:
    """Apply 0..2 noise functions with probability ``p`` each."""
    out = text
    for fn in _NOISE_FNS:
        if rng.random() < p:
            out = fn(out, rng) if fn is repeat_chars else fn(out)
    return re.sub(r"\s+", " ", out).strip()
