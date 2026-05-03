"""Render ontology records into a single Vietnamese chat reply.

Composition rule:
    [greeting?]  + [ontology block 1]  + ... + [ontology block N]   if entities found
    [greeting?]  + [out-of-domain]                                   otherwise

Within each ontology block the renderer uses a per-class template that is
tailored to the data the class actually exposes (e.g. an office card lists
contact fields, a procedure lists conditions / documents / steps).
"""

from __future__ import annotations

from .fuzzy import FuzzyMatch
from .queries import fetch


def _label_or_name(rec: dict) -> str:
    return rec.get("label") or rec["iri"].replace("_", " ")


def _bullets(items: list[dict], with_url: bool = False) -> str:
    lines: list[str] = []
    for it in items:
        text = it.get("label") or it.get("name", "").replace("_", " ")
        if with_url and it.get("url"):
            text = f"{text} ({it['url']})"
        lines.append(f"  • {text}")
    return "\n".join(lines)


def _render_quy_trinh(r: dict) -> str:
    out = [f"📘 {_label_or_name(r)}"]
    if r["description"]:
        out.append(r["description"])
    if r["based_on"]:
        out.append("• Căn cứ:")
        out.append(_bullets(r["based_on"], with_url=True))
    elif r["decision"]:
        out.append(f"• Căn cứ: {r['decision']}")
    if r["handled_by"]:
        out.append("• Phòng phụ trách:")
        out.append(_bullets(r["handled_by"]))
    if r["executed_via"]:
        out.append("• Thực hiện qua:")
        out.append(_bullets(r["executed_via"]))
    if r["conditions"]:
        out.append("• Điều kiện:")
        out.append(_bullets(r["conditions"]))
    if r["documents"]:
        out.append("• Biểu mẫu cần chuẩn bị:")
        out.append(_bullets(r["documents"], with_url=True))
    if r["steps"]:
        out.append("• Các bước:")
        out.append(_bullets(r["steps"]))
    if r["outputs"]:
        out.append("• Kết quả đầu ra:")
        out.append(_bullets(r["outputs"]))
    if r["fees"]:
        out.append("• Mức học phí áp dụng:")
        out.append(_bullets(r["fees"]))
    if r["payments"]:
        out.append("• Hình thức nộp:")
        out.append(_bullets(r["payments"]))
    if r["fee_note"]:
        out.append(f"• Ghi chú: {r['fee_note']}")
    if r["video_url"]:
        out.append(f"🎬 Video hướng dẫn: {r['video_url']}")
    return "\n".join(out)


def _render_phong_ban(r: dict) -> str:
    out = [f"🏢 {_label_or_name(r)}"]
    for label, key in (("Trưởng phòng", "head"), ("Email", "email"),
                       ("Địa chỉ", "location"), ("Điện thoại", "phone"),
                       ("Website", "website")):
        if r.get(key):
            out.append(f"• {label}: {r[key]}")
    return "\n".join(out)


def _render_tai_lieu(r: dict) -> str:
    out = [f"📄 {_label_or_name(r)}"]
    if r.get("form_url"):
        out.append(f"• Tải biểu mẫu: {r['form_url']}")
    return "\n".join(out)


def _render_dinh_muc(r: dict) -> str:
    out = [f"💰 {_label_or_name(r)}"]
    if r.get("fee_per_credit") is not None:
        out.append(f"• Đơn giá: {r['fee_per_credit']:,} đ/tín chỉ")
    if r.get("target"):
        out.append(f"• Áp dụng cho: {r['target']}")
    if r.get("decision"):
        out.append(f"• Căn cứ: {r['decision']}")
    if r.get("based_on"):
        out.append(_bullets(r["based_on"], with_url=True))
    return "\n".join(out)


def _render_phuong_thuc(r: dict) -> str:
    return f"💳 {_label_or_name(r)}"


_RENDERERS = {
    "QuyTrinhHocVu": _render_quy_trinh,
    "PhongBanHanhChinh": _render_phong_ban,
    "TaiLieuBieuMau": _render_tai_lieu,
    "DinhMucHocPhi": _render_dinh_muc,
    "PhuongThucThanhToan": _render_phuong_thuc,
}


def render_one(tag: str, iri: str) -> str | None:
    rec = fetch(tag, iri)
    if not rec:
        return None
    fn = _RENDERERS.get(tag)
    return fn(rec) if fn else None


def render_blocks(matches: list[tuple[str, FuzzyMatch]]) -> str:
    """Render multiple ``(tag, match)`` pairs; deduplicates by ``(tag, IRI)``."""
    seen: set[tuple[str, str]] = set()
    blocks: list[str] = []
    for tag, m in matches:
        key = (tag, m.iri)
        if key in seen:
            continue
        seen.add(key)
        block = render_one(tag, m.iri)
        if block:
            blocks.append(block)
    return "\n\n".join(blocks)


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


def compose(blocks: str, *, greeting: bool) -> str:
    """Compose the final reply.

    Rules:
        - a greeting prefix appears whenever ``greeting`` is ``True``;
        - ontology ``blocks`` are concatenated next when non-empty;
        - if neither applies, the out-of-domain fallback is returned.
    """
    parts: list[str] = []
    if greeting:
        parts.append(GREETING_REPLY)
    if blocks:
        parts.append(blocks)
    elif not greeting:
        parts.append(OUT_OF_DOMAIN_REPLY)
    return "\n\n".join(parts)
