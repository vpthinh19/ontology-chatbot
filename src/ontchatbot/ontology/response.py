"""Render ontology records into a single Vietnamese chat reply.

Composition rule (v2 — minimal-greeting policy):
    [ontology block 1]  ...  [ontology block N]   if any entities matched
    GREETING_REPLY                                  if user greeted but asked nothing else
    OUT_OF_DOMAIN_REPLY                             otherwise

The bot does NOT prepend a greeting to substantive answers; it greets back
only when the user's message is a pure greeting/closing with no recognised
entity. This matches typical chatbot UX expectations.

Within each ontology block the renderer uses a per-class template tailored
to the data the class actually exposes. Single-value fields are rendered
*inline* on the same bullet ("Phòng phụ trách: Phòng Tài chính") rather than
on a follow-up line, and URLs are emitted as markdown ``[label](url)`` links
which the frontend converts to clickable anchors.
"""

from __future__ import annotations

import logging

from .fuzzy import FuzzyMatch
from .queries import fetch

log = logging.getLogger(__name__)


def _label_or_name(rec: dict) -> str:
    return rec.get("label") or rec["iri"].replace("_", " ")


def _item_text(it: dict, with_url: bool = False) -> str:
    text = it.get("label") or it.get("name", "").replace("_", " ")
    if with_url and it.get("url"):
        return f"[{text}]({it['url']})"
    return text


def _section(header: str, items: list[dict], with_url: bool = False) -> str:
    """Render a "Header: items" section.

    Single-item sections collapse to one line ("• Header: item"). Multi-item
    sections use a sub-bullet on the next line, indented two spaces with an
    en-dash.
    """
    rendered = [_item_text(it, with_url=with_url) for it in items]
    if len(rendered) == 1:
        return f"• {header}: {rendered[0]}"
    bullets = "\n".join(f"  – {t}" for t in rendered)
    return f"• {header}:\n{bullets}"


def _md_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else label


def _render_quy_trinh(r: dict) -> str:
    out = [f"📘 {_label_or_name(r)}"]
    if r["description"]:
        out.append(r["description"])
    if r["based_on"]:
        out.append(_section("Căn cứ", r["based_on"], with_url=True))
    elif r["decision"]:
        out.append(f"• Căn cứ: {r['decision']}")
    if r["handled_by"]:
        out.append(_section("Phòng phụ trách", r["handled_by"]))
    if r["executed_via"]:
        out.append(_section("Thực hiện qua", r["executed_via"]))
    if r["conditions"]:
        out.append(_section("Điều kiện", r["conditions"]))
    if r["documents"]:
        out.append(_section("Biểu mẫu cần chuẩn bị", r["documents"], with_url=True))
    if r["steps"]:
        out.append(_section("Các bước", r["steps"]))
    if r["outputs"]:
        out.append(_section("Kết quả đầu ra", r["outputs"]))
    if r["fees"]:
        out.append(_section("Mức học phí áp dụng", r["fees"]))
    if r["payments"]:
        out.append(_section("Hình thức nộp", r["payments"]))
    if r["fee_note"]:
        out.append(f"• Ghi chú: {r['fee_note']}")
    if r["video_url"]:
        out.append(f"🎬 Video hướng dẫn: {_md_link('xem hướng dẫn', r['video_url'])}")
    return "\n".join(out)


def _render_phong_ban(r: dict) -> str:
    out = [f"🏢 {_label_or_name(r)}"]
    for label, key in (("Trưởng phòng", "head"), ("Email", "email"),
                       ("Địa chỉ", "location"), ("Điện thoại", "phone")):
        if r.get(key):
            out.append(f"• {label}: {r[key]}")
    if r.get("website"):
        out.append(f"• Website: {_md_link(r['website'], r['website'])}")
    return "\n".join(out)


def _render_tai_lieu(r: dict) -> str:
    out = [f"📄 {_label_or_name(r)}"]
    if r.get("form_url"):
        out.append(f"• Tải biểu mẫu: {_md_link('tải tại đây', r['form_url'])}")
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
        out.append(_section("Tham chiếu", r["based_on"], with_url=True))
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
            log.debug("[render] dedupe tag=%s iri=%s", tag, m.iri)
            continue
        seen.add(key)
        block = render_one(tag, m.iri)
        if block:
            blocks.append(block)
            log.info("[render] tag=%s iri=%s chars=%d", tag, m.iri, len(block))
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

    Rules (minimal-greeting policy):
        - if there are entity blocks → return blocks alone (no greeting prefix);
        - else if user greeted → return GREETING_REPLY;
        - else → return OUT_OF_DOMAIN_REPLY.
    """
    if blocks:
        return blocks
    if greeting:
        return GREETING_REPLY
    return OUT_OF_DOMAIN_REPLY
