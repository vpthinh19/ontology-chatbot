"""Render: ``act`` + :class:`KetQua` → câu trả lời tiếng Việt (DESIGN.md §4).

Pha cuối của pipeline: xử lý chào hỏi/ngoại lệ và ghép kết quả duyệt thành chuỗi cho UI.
**Giọng nghiêm túc, cứng, KHÔNG gợi mở** (chatbot học vụ). Không phụ thuộc owlready2 —
chỉ format `OntNode`/`GiaTri`, nên test chạy trên dataclass thuần.
"""

from __future__ import annotations

from .ontology import GiaTri, KetQua, OntNode
from .preprocess import is_url
from .tree import GREETING, OOD, QUERY, VAGUE, Cay

GREETING_REPLY = "Xin chào. Đây là hệ thống tra cứu thủ tục học vụ Trường Đại học Nha Trang."
OOD_REPLY = "Không có thông tin."
VAGUE_REPLY = "Không hiểu câu hỏi."

# data-prop local name → tiêu đề hiển thị, theo thứ tự. Prop ngoài bảng xếp sau, vẫn hiện.
_HEADER: dict[str, str] = {
    "noiDung": "Nội dung",
    "ghiChuHocPhi": "Lưu ý",
    "hocPhiMoiTinChi": "Học phí mỗi tín chỉ",
    "truongPhong": "Phụ trách",
    "diaDiem": "Địa chỉ",
    "email": "Email",
    "soDienThoai": "Điện thoại",
    "website": "Website",
    "duongDanBieuMau": "Tải biểu mẫu",
}
_ORDER = list(_HEADER)
_PARAGRAPH = frozenset({"noiDung", "ghiChuHocPhi"})   # văn xuôi, render không bullet


def render_reply(cay: Cay, kq: KetQua) -> str:
    """act thắng trước; trong ``query`` thì dữ liệu thắng, không có → 'không có thông tin'."""
    if cay.act == GREETING:
        return GREETING_REPLY
    if cay.act == OOD:
        return OOD_REPLY
    if cay.act == VAGUE:
        return VAGUE_REPLY
    # query
    blocks = [_render_value(v) for v in kq.values]
    if kq.nodes:
        blocks.append(_render_nodes(kq.nodes))
    blocks = [b for b in blocks if b]
    if blocks:
        return "\n".join(blocks)
    if kq.misses:
        labels = ", ".join(f"«{m}»" for m in _dedup(kq.misses))
        return f"Không có thông tin {labels}."
    return OOD_REPLY


def _render_value(gt: GiaTri) -> str:
    """Một lá data → một dòng (hoặc văn xuôi với noiDung/ghiChú)."""
    header = _HEADER.get(gt.prop, gt.prop)
    if gt.prop in _PARAGRAPH:
        return "\n".join(str(v).strip() for v in gt.values)
    return f"{header}: " + ", ".join(_field_value(gt.prop, v) for v in gt.values)


def _render_nodes(nodes: list[OntNode]) -> str:
    if len(nodes) == 1:
        return _render_node(nodes[0])
    items = [_render_node(n, bullet="•") for n in nodes]
    sep = "\n\n" if any("\n" in it for it in items) else "\n"
    return sep.join(items)


def _render_node(node: OntNode, *, bullet: str = "") -> str:
    head = f"{bullet} {node.label}".strip() if bullet else node.label
    lines = [head]
    for key in _ordered_keys(node.data):
        value = node.data[key]
        if value in (None, "", []):
            continue
        if key in _PARAGRAPH:
            lines.append(f"   {_HEADER.get(key, key)}: {value}")
        else:
            lines.append("   - " + _format_field(key, value))
    return "\n".join(lines)


def _ordered_keys(data: dict) -> list[str]:
    known = [k for k in _ORDER if k in data]
    rest = [k for k in data if k not in _HEADER]
    return known + rest


def _format_field(key: str, value) -> str:
    header = _HEADER.get(key, key)
    if isinstance(value, list):
        return f"{header}: " + ", ".join(_field_value(key, v) for v in value)
    return f"{header}: {_field_value(key, value)}"


def _field_value(key: str, value) -> str:
    if key == "hocPhiMoiTinChi" and isinstance(value, (int, float)):
        return f"{int(value):,} đ/tín chỉ".replace(",", ".")
    if is_url(value):
        return _safe_url(str(value))
    return _scalar(value)


def _scalar(v) -> str:
    if isinstance(v, bool):
        return "Có" if v else "Không"
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".")
    return str(v)


def _safe_url(url: str) -> str:
    return url.replace("(", "%28").replace(")", "%29")


def _dedup(items) -> list[str]:
    seen: set[str] = set()
    return [x for x in items if not (x in seen or seen.add(x))]
