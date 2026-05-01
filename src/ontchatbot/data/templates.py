"""Sentence templates and surface-noise functions for synthetic NER data.

Only the *generation-time* templates live here — SPARQL strings are owned by
``ontology.queries`` and the reply formats by ``ontology.response``. Each
template has exactly one ``{E}`` slot; multi-entity samples are produced by
stitching two single-entity sentences with conversational connectors. Noise
functions inject realistic Vietnamese chat distortions so the trained model
generalises to typos, casing perturbations, and missing diacritics.
"""

from __future__ import annotations

import random
import re

# Per-class question/statement scaffolds with a single ``{E}`` entity slot.
TEMPLATES: dict[str, list[str]] = {
    "QuyTrinhHocVu": [
        "{E} làm thế nào ạ", "{E} thực hiện ra sao", "cho em hỏi {E} với",
        "em muốn biết về {E}", "quy trình {E} là gì", "{E} cần làm gì",
        "{E} có thời hạn không", "muốn {E} thì sao", "hướng dẫn {E} chi tiết",
        "{E} nộp ở đâu", "anh chị ơi {E} cần giấy tờ gì", "em năm 2 muốn {E}",
        "{E} liên hệ phòng nào", "{E} mất bao lâu", "{E} có mất phí không",
        "{E} đăng ký kiểu gì", "trường mình {E} ra sao", "{E} có được không",
        "có ai biết {E} không", "{E} đợt này còn kịp không", "{E} thủ tục gì",
        "ai phụ trách {E}", "{E} điều kiện thế nào", "{E}", "mình cần {E}",
    ],
    "PhongBanHanhChinh": [
        "cho mình xin số {E}", "{E} ở đâu ạ", "liên hệ {E} sao",
        "địa chỉ {E} là gì", "{E} làm việc giờ nào", "email {E}",
        "{E} có website không", "trưởng {E} là ai", "muốn gặp {E}",
        "{E} số điện thoại bao nhiêu", "{E} ở tầng mấy", "{E} thứ bảy có làm không",
        "ai phụ trách bên {E}", "{E} hỗ trợ những gì", "em cần gặp {E}",
        "{E}", "{E} tiếp dân không",
    ],
    "TaiLieuBieuMau": [
        "cho em xin {E}", "{E} tải ở đâu", "link {E} ạ", "em cần file {E}",
        "{E} mẫu mới nhất", "biểu mẫu {E} ở đâu", "{E} điền sao",
        "có {E} không ạ", "thầy cô gửi em {E}", "{E} nộp ở đâu",
        "{E} có sẵn online không", "{E} có cần chữ ký không", "{E}",
    ],
    "DinhMucHocPhi": [
        "{E} bao nhiêu", "{E} 1 tín chỉ giá nhiêu", "{E} sao ạ",
        "{E} đóng bao nhiêu", "ngành em {E}", "{E} năm nay tăng không",
        "{E} có giảm không", "cho hỏi {E}", "{E} thế nào",
        "{E} áp dụng cho ngành nào", "{E} căn cứ quyết định nào",
        "{E}", "em muốn biết {E}",
    ],
    "PhuongThucThanhToan": [
        "đóng học phí qua {E} được không", "{E} có hỗ trợ không",
        "muốn dùng {E}", "trường mình chấp nhận {E} chứ", "{E} thế nào",
        "có thể trả bằng {E}", "{E} có phí không", "{E}",
    ],
}

# Connectors used to splice two single-entity sentences into one multi-entity one.
CONNECTORS: tuple[str, ...] = (" còn ", " thêm ", " và ", " , ", " với cả ")

# Short greetings and closings — label-wide ``O``.
GREETINGS: list[str] = [
    "xin chào ạ", "chào thầy cô", "hello ạ", "hi mọi người",
    "em chào ạ", "cảm ơn nhiều", "thanks nhé", "tks ạ", "tạm biệt",
    "bye bye", "hẹn gặp lại", "chào buổi sáng", "ok cảm ơn",
    "dạ vâng cảm ơn", "alo có ai không", "chào shop",
]

# Out-of-domain conversational queries.
OUT_OF_DOMAIN: list[str] = [
    "thời tiết hôm nay thế nào", "có món gì ngon ở Nha Trang không",
    "trận bóng tối qua ai thắng", "kể chuyện cười cho em nghe",
    "hôm nay là ngày bao nhiêu", "đồng phục trường mua ở đâu",
    "ký túc xá có còn chỗ không", "câu lạc bộ sinh hoạt khi nào",
    "quán cà phê gần trường", "xe bus tuyến nào đến trường",
    "thư viện mở cửa lúc mấy giờ", "bãi giữ xe sinh viên ở đâu",
    "hôm nay ăn gì", "trường có dịch vụ in ấn không",
    "wifi trường mật khẩu là gì", "ai là hiệu trưởng đầu tiên",
    "giải bóng đá khoa bao giờ", "trường mình thành lập năm nào",
    "ngày mai có lễ hội gì", "tôi muốn đặt vé máy bay",
]


# Surface noise

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
assert len(_VOWELS) == len(_PLAIN), (len(_VOWELS), len(_PLAIN))
_DIACRITIC_TABLE = str.maketrans(_VOWELS + _VOWELS.upper(), _PLAIN + _PLAIN.upper())


def strip_diacritics(s: str) -> str:
    return s.translate(_DIACRITIC_TABLE)


def perturb(text: str, rng: random.Random, p: float = 0.3) -> str:
    """Apply a few independent surface distortions with probability ``p``."""
    out = text
    if rng.random() < p:
        out = strip_diacritics(out)
    if rng.random() < p:
        out = out.lower()
    if rng.random() < p:
        out = re.sub(r"\s+([?,.!:;])", r"\1", out).rstrip("?.!,;:")
    return re.sub(r"\s+", " ", out).strip()
