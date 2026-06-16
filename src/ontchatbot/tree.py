"""Hợp đồng CÂY JSON do model sinh ra (DESIGN.md §3) — data contract model↔ontology.

ViT5 sinh một dict ``{"act", "entities"}``; module này **chỉ** kiểm tra hợp lệ và dựng
thành cây Python (`Tree`) cho `ontology.traverse`. Không có luật hiểu-câu ở đây (§9) —
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

from dataclasses import dataclass

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
_KINDS = frozenset({INDIVIDUAL, OBJECT, DATA})


@dataclass(frozen=True)
class TreeNode:
    """Một node của cây truy vấn. ``kind`` quyết định cách `ontology` khớp + xử lý."""
    label: str
    kind: str
    children: tuple["TreeNode", ...] = ()


@dataclass(frozen=True)
class Tree:
    """Cây truy vấn đã validate. ``root=None`` khi act không phải query / JSON hỏng."""
    act: str
    root: TreeNode | None = None


def parse(obj: object) -> Tree:
    """Dict thô từ model → :class:`Tree`. Khoan dung lỗi: JSON/loại sai → ``vague``.

    Quy tắc loại node ma (§8): node có ``label`` rỗng, hoặc ``type`` không hợp lệ, hoặc
    (với gốc) không phải ``individual`` → coi như không dựng được cây → trả ``vague``.
    Con hỏng bị bỏ lặng lẽ; nhánh vẫn đi tiếp với các con hợp lệ.
    """
    if not isinstance(obj, dict):
        return Tree(act=VAGUE)
    act = obj.get("act")
    if act not in _ACTS:
        return Tree(act=VAGUE)
    if act != QUERY:
        return Tree(act=act)                      # greeting/ood/vague: render lo, không cần cây

    entities = obj.get("entities")
    if not isinstance(entities, list) or not entities:
        return Tree(act=VAGUE)                     # query mà không có chủ thể → mơ hồ
    root = _node(entities[0])                       # một truy vấn = một cây (lấy cây đầu)
    if root is None or root.kind != INDIVIDUAL:
        return Tree(act=VAGUE)                      # gốc phải là individual (§3)
    return Tree(act=QUERY, root=root)


def _node(raw: object) -> TreeNode | None:
    """Dựng một node; trả ``None`` nếu hỏng (caller bỏ qua)."""
    if not isinstance(raw, dict):
        return None
    label = raw.get("label")
    kind = raw.get("type")
    if not isinstance(label, str) or not label.strip() or kind not in _KINDS:
        return None
    children_raw = raw.get("children") or []
    if not isinstance(children_raw, list):
        children_raw = []
    children = tuple(n for n in (_node(c) for c in children_raw) if n is not None)
    # data là lá (§3): bỏ mọi con nếu lỡ có.
    if kind == DATA:
        children = ()
    return TreeNode(label=label.strip(), kind=kind, children=children)
