"""Render fetched ontology records into a Vietnamese reply.

The pipeline may surface multiple individuals (one per recognised entity span);
records are deduplicated by IRI and concatenated with section separators so the
final message remains coherent even for multi-entity queries.
"""

from __future__ import annotations

from .fuzzy import FuzzyMatch
from .queries import fetch


def _humanize(iri: str) -> str:
    return iri.replace("_", " ").strip()


def _render_quy_trinh(rec: dict) -> str:
    name = _humanize(rec["iri"])
    parts: list[str] = [f"📘 Quy trình: {name}"]
    if rec.get("description"):
        parts.append(rec["description"])
    if rec.get("decision"):
        parts.append(f"• Căn cứ: {rec['decision']}")
    if rec.get("handled_by"):
        parts.append("• Phòng phụ trách: " + ", ".join(_humanize(x) for x in rec["handled_by"]))
    if rec.get("executed_via"):
        parts.append("• Thực hiện qua: " + ", ".join(_humanize(x) for x in rec["executed_via"]))
    if rec.get("documents"):
        parts.append("• Biểu mẫu liên quan: " + ", ".join(_humanize(x) for x in rec["documents"]))
    if rec.get("conditions"):
        parts.append("• Điều kiện: " + ", ".join(_humanize(x) for x in rec["conditions"]))
    if rec.get("outputs"):
        parts.append("• Kết quả: " + ", ".join(_humanize(x) for x in rec["outputs"]))
    if rec.get("video_url"):
        parts.append(f"• Video hướng dẫn: {rec['video_url']}")
    return "\n".join(parts)


def _render_phong_ban(rec: dict) -> str:
    name = _humanize(rec["iri"])
    lines = [f"🏢 {name}"]
    for label, key in [
        ("Trưởng phòng", "head"), ("Email", "email"), ("Địa chỉ", "location"),
        ("Điện thoại", "phone"), ("Website", "website"),
    ]:
        if rec.get(key):
            lines.append(f"• {label}: {rec[key]}")
    return "\n".join(lines)


def _render_tai_lieu(rec: dict) -> str:
    name = _humanize(rec["iri"])
    out = f"📄 Biểu mẫu: {name}"
    if rec.get("form_url"):
        out += f"\n• Tải về: {rec['form_url']}"
    return out


def _render_dinh_muc(rec: dict) -> str:
    name = _humanize(rec["iri"])
    lines = [f"💰 Định mức học phí: {name}"]
    if rec.get("fee_per_credit") is not None:
        lines.append(f"• Đơn giá: {rec['fee_per_credit']:,} đ/tín chỉ")
    if rec.get("target"):
        lines.append(f"• Áp dụng: {rec['target']}")
    if rec.get("decision"):
        lines.append(f"• Căn cứ: {rec['decision']}")
    if rec.get("note"):
        lines.append(f"• Ghi chú: {rec['note']}")
    return "\n".join(lines)


def _render_phuong_thuc(rec: dict) -> str:
    return f"💳 Phương thức thanh toán: {_humanize(rec['iri'])}"


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


def render_many(matches: list[tuple[str, FuzzyMatch]]) -> str:
    """Render multiple (tag, match) pairs into a single message; deduplicates by IRI."""
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
    if not blocks:
        return "Xin lỗi, mình chưa có thông tin phù hợp với câu hỏi của bạn."
    return "\n\n".join(blocks)


def greeting_reply() -> str:
    return "Xin chào! Mình có thể hỗ trợ bạn về quy trình học vụ, phòng ban, học phí, biểu mẫu… Bạn cần tra cứu gì?"


def out_of_domain_reply() -> str:
    return ("Câu hỏi của bạn nằm ngoài phạm vi tri thức hiện có của mình. "
            "Hãy thử hỏi về quy trình học vụ, phòng ban hành chính, học phí hoặc biểu mẫu.")
