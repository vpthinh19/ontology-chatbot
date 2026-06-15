"""Render ``Fact[]`` → a Vietnamese chat reply.

The answer layer already produced edge-correct blocks, so the renderer only
formats nodes — no owlready2 dependency, tests run on plain dataclasses. Three
block shapes: a **class listing** (``cls`` set), a **self-description** (no
heading → the node's full data, no bullet), and a **group block** (heading +
bulleted nodes, the cohort×program / relation results).

Greeting / out-of-domain are policy, not data: an empty fact list with a
``GREETING`` act greets; an empty list otherwise apologises with scope. When
the query named a second subject (scope = one subject/query), a closing line
invites the user to ask that part separately.
"""

from __future__ import annotations

from .answer import Fact
from .graph import Node
from .nlu import GREETING, Query
from .text import is_url

GREETING_REPLY = (
    "Xin chào! Mình có thể tra cứu giúp bạn về quy trình học vụ, phòng ban "
    "hành chính, định mức học phí, biểu mẫu hoặc phương thức thanh toán. "
    "Bạn cần hỏi gì ạ?"
)
OUT_OF_DOMAIN_REPLY = (
    "Câu hỏi của bạn nằm ngoài phạm vi tri thức hiện có. Hãy thử hỏi về quy "
    "trình học vụ, phòng ban hành chính, học phí, biểu mẫu hoặc phương thức "
    "thanh toán."
)

# Data-property local name → header, in display order. Unlisted props are
# appended in declaration order, so a new property in Protégé still shows.
_DATA_LABEL: dict[str, str] = {
    "moTaQuyTrinh": "Mô tả",
    "ghiChuHocPhi": "Lưu ý",
    "hocPhiMoiTinChi": "Học phí mỗi tín chỉ",
    "truongPhong": "Phụ trách",
    "diaDiem": "Địa chỉ",
    "email": "Email",
    "soDienThoai": "Điện thoại",
    "website": "Website",
    "duongDanBieuMau": "Tải biểu mẫu",
}
_DATA_ORDER = list(_DATA_LABEL)

# Props consumed programmatically or already conveyed by the label (the
# condition prose carries its own threshold) — never shown as raw fields.
_HIDDEN_DATA = frozenset({
    "chiSoDo", "toanTuSoSanh", "giaTriNguong", "laDinhLuong",
    "noiDungDieuKien", "maKhoa",
})

# v9 class IRIs (Vietnamese) → human label for listings / the closing notice.
_CLASS_LABEL: dict[str, str] = {
    "QuyTrinhHocVu": "quy trình học vụ",
    "PhongBanHanhChinh": "phòng ban hành chính",
    "TaiLieuBieuMau": "biểu mẫu",
    "DinhMucHocPhi": "định mức học phí",
    "PhuongThucThanhToan": "phương thức thanh toán",
    "DieuKien": "điều kiện",
    "KetQuaDauRa": "kết quả",
    "QuyDinh": "quy định",
    "Khoa": "khóa",
    "Nganh": "ngành",
}


def render_reply(query: Query, facts: list[Fact]) -> str:
    """Final reply policy: facts win; else greeting vs out-of-domain by act."""
    if not facts:
        return GREETING_REPLY if query.act == GREETING else OUT_OF_DOMAIN_REPLY
    blocks = [b for b in (_render_fact(f) for f in facts) if b]
    if not blocks:
        return OUT_OF_DOMAIN_REPLY
    reply = "\n---\n".join(blocks)
    if query.extra_subjects:
        labels = ", ".join(f"«{_CLASS_LABEL.get(c, c)}»" for c in query.extra_subjects)
        reply += (f"\n\n(Câu hỏi của bạn còn nhắc tới {labels} — bạn hỏi riêng "
                  "ý đó giúp mình nhé.)")
    return reply


def _render_fact(f: Fact) -> str:
    if f.cls:
        return _render_listing(f)
    lines: list[str] = []
    if f.heading:
        lines.append(f"{f.heading}:")
    if f.note:
        lines.append(f.note)
    if f.objects:
        lines.append(_render_objects(f))
    return "\n".join(l for l in lines if l)


def _render_listing(f: Fact) -> str:
    head = f"Các {_CLASS_LABEL.get(f.cls, 'mục')} hiện có:"
    return "\n".join([head, *(f"• {n.label}" for n in f.objects)])


def _render_objects(f: Fact) -> str:
    """Bulleted nodes under a heading; or a single node's full data (no bullet)
    for the self-description block (no heading)."""
    if not f.heading and len(f.objects) == 1:
        return _render_node(f.objects[0])
    items = [_render_node(n, bullet="•") for n in f.objects]
    sep = "\n\n" if any("\n" in it for it in items) else "\n"
    return sep.join(items)


def _render_node(node: Node, *, bullet: str = "") -> str:
    """Label + its data fields (ordered). ``bullet`` prefixes the label when
    the node is a list item under a header."""
    head = f"{bullet} {node.label}".strip() if bullet else node.label
    lines = [head]
    for key in _ordered_keys(node.data):
        value = node.data[key]
        if value in (None, "", []):
            continue
        lines.append("    " + _format_field(key, value))
    return "\n".join(lines)


def _ordered_keys(data: dict) -> list[str]:
    known = [k for k in _DATA_ORDER if k in data]
    rest = [k for k in data if k not in _DATA_LABEL and k not in _HIDDEN_DATA]
    return known + rest


def _format_field(key: str, value) -> str:
    header = _DATA_LABEL.get(key, key)
    if key == "hocPhiMoiTinChi" and isinstance(value, (int, float)):
        return f"- {header}: {int(value):,} đ/tín chỉ".replace(",", ".")
    if isinstance(value, list):
        return f"- {header}: " + ", ".join(_scalar(v) for v in value)
    if is_url(value):
        return f"- {header}: [{header}]({_safe_url(value)})"
    return f"- {header}: {_scalar(value)}"


def _scalar(v) -> str:
    if isinstance(v, bool):
        return "Có" if v else "Không"
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return str(v)


def _safe_url(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29")
