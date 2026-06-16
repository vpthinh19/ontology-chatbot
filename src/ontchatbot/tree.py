"""Hợp đồng CÂY JSON do model sinh ra (DESIGN.md §3) — data contract model↔ontology.

ViT5 sinh một dict ``{"act", "entities"}``; module này **chỉ** kiểm tra hợp lệ và dựng
thành cây Python (`Cay`) cho `ontology.traverse`. Không có luật hiểu-câu ở đây (§9) —
chỉ validate cấu trúc và **loại node ma** (label rỗng / loại sai) để hệ không gãy (§8).

Hình dạng cây (mục §3)::

    { "act": "query",
      "entities": [ {"label": "học phí", "type": "individual", "children": [
                      {"label": "k65", "type": "individual", "children": [...]} ]} ] }

- ``act`` ∈ {query, greeting, ood, vague}. Chỉ ``query`` mới chạy duyệt.
- Mỗi node: ``label`` (đoạn chữ), ``type`` ∈ {individual, object, data}, ``children`` (cây con).
- ``entities`` là **một cây** (một chủ thể / truy vấn); **gốc luôn ``individual``**.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# act hợp lệ (DESIGN.md §4).
QUERY = "query"
GREETING = "greeting"
OOD = "ood"
VAGUE = "vague"
_ACTS = frozenset({QUERY, GREETING, OOD, VAGUE})

# loại node hợp lệ (thuật ngữ OWL, DESIGN.md §3).
INDIVIDUAL = "individual"
OBJECT = "object"
DATA = "data"
_LOAI = frozenset({INDIVIDUAL, OBJECT, DATA})


@dataclass(frozen=True)
class CayNode:
    """Một node của cây truy vấn. ``loai`` quyết định cách `ontology` khớp + xử lý."""
    label: str
    loai: str
    con: tuple["CayNode", ...] = ()


@dataclass(frozen=True)
class Cay:
    """Cây truy vấn đã validate. ``goc=None`` khi act không phải query / JSON hỏng."""
    act: str
    goc: CayNode | None = None


def parse(obj: object) -> Cay:
    """Dict thô từ model → :class:`Cay`. Khoan dung lỗi: JSON/loại sai → ``vague``.

    Quy tắc loại node ma (§8): node có ``label`` rỗng, hoặc ``type`` không hợp lệ, hoặc
    (với gốc) không phải ``individual`` → coi như không dựng được cây → trả ``vague``.
    Con hỏng bị bỏ lặng lẽ; nhánh vẫn đi tiếp với các con hợp lệ.
    """
    if not isinstance(obj, dict):
        return Cay(act=VAGUE)
    act = obj.get("act")
    if act not in _ACTS:
        return Cay(act=VAGUE)
    if act != QUERY:
        return Cay(act=act)                       # greeting/ood/vague: render lo, không cần cây

    entities = obj.get("entities")
    if not isinstance(entities, list) or not entities:
        return Cay(act=VAGUE)                      # query mà không có chủ thể → mơ hồ
    goc = _node(entities[0])                       # một truy vấn = một cây (lấy cây đầu)
    if goc is None or goc.loai != INDIVIDUAL:
        return Cay(act=VAGUE)                       # gốc phải là individual (§3)
    return Cay(act=QUERY, goc=goc)


def _node(raw: object) -> CayNode | None:
    """Dựng một node; trả ``None`` nếu hỏng (caller bỏ qua)."""
    if not isinstance(raw, dict):
        return None
    label = raw.get("label")
    loai = raw.get("type")
    if not isinstance(label, str) or not label.strip() or loai not in _LOAI:
        return None
    children_raw = raw.get("children") or []
    if not isinstance(children_raw, list):
        children_raw = []
    con = tuple(n for n in (_node(c) for c in children_raw) if n is not None)
    # data là lá (§3): bỏ mọi con nếu lỡ có.
    if loai == DATA:
        con = ()
    return CayNode(label=label.strip(), loai=loai, con=con)
