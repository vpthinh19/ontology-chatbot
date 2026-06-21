"""Dựng KHO PHIẾU PHẲNG từ ontology cho baseline truy hồi (Phase 8).

Mỗi cá thể → MỘT phiếu, **id = IRI** (khớp ontology để chấm chung mức IRI). Nội dung là văn
xuôi tiếng Việt **trung thành tuyệt đối** với fact ontology (sinh chương-trình, không LLM → tái
lập được, không bịa): chỉ thông tin của CHÍNH cá thể (nhãn + alias + phân loại + giá trị data),
**loại bỏ mọi quan hệ** — đó chính là điểm yếu cấu trúc mà benchmark phơi ra. Phiếu fee chứa đủ
**facet** (mã khoá + tên/alias ngành) nên truy vấn lọc-giao có cơ hội công bằng (phẳng thua là do
thiếu suy luận, không phải lỗi dựng phiếu — Codex review #4).

(Lịch sử: từng có biến thể ``denorm`` nhồi quan-hệ làm cận-trên; đã BỎ 2026-06-21 — chỉ giữ MỘT
kho phẳng thực-tế để câu chuyện gọn: người đọc chỉ cần "ontology vs phẳng".)
"""

from __future__ import annotations

from ..ontology import Ontology, _ALIAS_PROP


def _values(ind, prop) -> list[str]:
    return [str(v) for v in (getattr(ind, prop, []) or [])]


def _own_facts(ont: Ontology, ind) -> list[str]:
    """Các câu fact của CHÍNH cá thể (nhãn, alias, phân loại, giá trị data)."""
    label = ont._label_of(ind)
    parts = [f"{label}."]
    aliases = _values(ind, _ALIAS_PROP)
    if aliases:
        parts.append(f"Còn gọi là: {', '.join(aliases)}.")
    parts.append(f"Phân loại: {ont.class_label(ont._class_of(ind))}.")
    for prop in ont._data_props:
        if prop == _ALIAS_PROP:
            continue
        vals = _values(ind, prop)
        if vals:
            parts.append(f"{ont.property_label(prop)}: {', '.join(vals)}.")
    return parts


def build_corpus(ont: Ontology) -> dict[str, str]:
    """IRI → văn bản phiếu phẳng (fact của CHÍNH cá thể, loại bỏ mọi quan hệ)."""
    return {ind.name: " ".join(_own_facts(ont, ind)) for ind in ont._owl.individuals()}
