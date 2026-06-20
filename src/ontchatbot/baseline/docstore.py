"""Dựng KHO PHIẾU phẳng từ ontology cho baseline truy hồi (Phase 8).

Mỗi cá thể → MỘT phiếu, **id = IRI** (khớp ontology để chấm chung mức IRI). Nội dung là văn
xuôi tiếng Việt **trung thành tuyệt đối** với fact ontology (sinh chương-trình, không LLM → tái
lập được, không bịa). Hai biến thể (báo cáo riêng — Codex review #7):

* ``concise`` — baseline **tài liệu thực-tế**: chỉ thông tin của CHÍNH cá thể (nhãn + alias +
  phân loại + các giá trị data của nó). Phiếu fee chứa đủ **facet** (mã khoá + tên/alias ngành)
  nên truy vấn GIAO có cơ hội công bằng — phẳng thua giao-tập là do thiếu suy luận, không phải lỗi
  dựng phiếu (Codex review #4).
* ``denorm`` — **chỉ mục phẳng vật-chất-hoá-từ-ontology** (upper-bound, KHÔNG phải tài liệu tự
  nhiên): concise + nhồi quan-hệ ĐI RA (láng giềng + thuộc tính của chúng) và quan-hệ ĐẾN (ai trỏ
  tới mình, qua quan-hệ gì). Nhờ incoming, phiếu chủ-thể-đáp-án (vd Phòng CTSV) tự chứa ngữ cảnh
  đa-hop ("được xử lý-bởi trong: Bảo lưu") → phẳng có cơ may bắt đa-hop mà KHÔNG phá định nghĩa gold.

⚠️ ``denorm`` đặt sẵn đáp án multi-hop dưới dạng văn xuôi ⇒ gọi đúng tên là "ontology-materialized
index", coi là cận-trên truy hồi, KHÔNG dùng làm baseline chính duy nhất.
"""

from __future__ import annotations

from ..ontology import Ontology, _ALIAS_PROP

CONCISE = "concise"
DENORM = "denorm"
VARIANTS = (CONCISE, DENORM)


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


def _outgoing_facts(ont: Ontology, ind) -> list[str]:
    """Quan-hệ ĐI RA: với mỗi object-property, láng giềng + thuộc tính data của láng giềng."""
    parts: list[str] = []
    for prop in ont._obj_props:
        chunks = []
        for niri in ont._neighbors(ind.name, prop):
            n = ont._owl[niri]
            if n is None:
                continue
            ndata = [f"{ont.property_label(p)} {', '.join(_values(n, p))}"
                     for p in ont._data_props if p != _ALIAS_PROP and _values(n, p)]
            nlabel = ont._label_of(n)
            chunks.append(f"{nlabel} ({'; '.join(ndata)})" if ndata else nlabel)
        if chunks:
            parts.append(f"{ont.property_label(prop)}: {', '.join(chunks)}.")
    return parts


def _incoming_index(ont: Ontology) -> dict[str, list[str]]:
    """IRI đích → các câu 'được [nhãn-quan-hệ] trong: [nhãn nguồn]' (quan-hệ ĐẾN)."""
    incoming: dict[str, list[str]] = {}
    for src in ont._owl.individuals():
        slabel = ont._label_of(src)
        for prop in ont._obj_props:
            plabel = ont.property_label(prop)
            for niri in ont._neighbors(src.name, prop):
                incoming.setdefault(niri, []).append(f"{slabel} ({plabel})")
    return incoming


def build_corpus(ont: Ontology, variant: str = CONCISE) -> dict[str, str]:
    """IRI → văn bản phiếu. ``concise`` = fact của chính cá thể; ``denorm`` = + láng giềng/incoming."""
    if variant not in VARIANTS:
        raise ValueError(f"variant phải ∈ {VARIANTS}, nhận {variant!r}")
    incoming = _incoming_index(ont) if variant == DENORM else {}
    corpus: dict[str, str] = {}
    for ind in ont._owl.individuals():
        parts = _own_facts(ont, ind)
        if variant == DENORM:
            parts += _outgoing_facts(ont, ind)
            inc = incoming.get(ind.name, [])
            if inc:
                parts.append(f"Được nhắc tới trong: {', '.join(inc)}.")
        corpus[ind.name] = " ".join(parts)
    return corpus
