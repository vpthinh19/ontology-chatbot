"""Hợp đồng CÂY JSON do model sinh ra (DESIGN.md §3) — data contract model↔ontology.

BARTpho sinh một dict ``{"act", "entities"}``; module này **chỉ** kiểm tra hợp lệ và dựng
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

import json
import re
from dataclasses import dataclass

from .preprocess import normalize_tone

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


class StrictParseError(ValueError):
    """Cây không hợp lệ ở chế độ NGHIÊM (oracle validate dataset Phase 4).

    Khác :func:`parse` (khoan dung cho production — bỏ lặng node hỏng): bản nghiêm
    *từ chối* mọi bất thường để cây dataset không lọt lỗi cấu trúc (REVIEW §C5). Thông
    điệp ghi ``path`` (vd ``entities[0].children[1]``) để soạn dataset dễ sửa.
    """


def parse_strict(obj: object) -> Tree:
    """Như :func:`parse` nhưng RAISE :class:`StrictParseError` thay vì khoan dung.

    Bắt đúng các lỗi REVIEW §C5 mà ``parse`` nuốt lặng:
    * node không phải dict / ``label`` rỗng / ``type`` sai / ``children`` không phải list;
    * node ``data`` có con (data là lá §3);
    * ``query`` không có hoặc có **>1** chủ thể (một truy vấn = một cây §3);
    * gốc không phải ``individual``;
    * ``act`` sai, hoặc act phi-``query`` lại kèm ``entities``.
    """
    if not isinstance(obj, dict):
        raise StrictParseError(f"gốc phải là dict, gặp {type(obj).__name__}")
    act = obj.get("act")
    if act not in _ACTS:
        raise StrictParseError(f"act không hợp lệ: {act!r}")
    entities = obj.get("entities")
    if act != QUERY:
        if entities:
            raise StrictParseError(f"act={act!r} không được kèm entities")
        return Tree(act=act)
    if not isinstance(entities, list) or not entities:
        raise StrictParseError("query phải có đúng 1 chủ thể, gặp rỗng")
    if len(entities) != 1:
        raise StrictParseError(f"query phải có đúng 1 chủ thể, gặp {len(entities)}")
    root = _node_strict(entities[0], "entities[0]")
    if root.kind != INDIVIDUAL:
        raise StrictParseError(f"gốc phải là individual, gặp {root.kind!r}")
    return Tree(act=QUERY, root=root)


def _node_strict(raw: object, path: str) -> TreeNode:
    """Dựng một node ở chế độ nghiêm; RAISE với ``path`` khi hỏng."""
    if not isinstance(raw, dict):
        raise StrictParseError(f"{path}: node phải là dict, gặp {type(raw).__name__}")
    label = raw.get("label")
    if not isinstance(label, str) or not label.strip():
        raise StrictParseError(f"{path}: label rỗng/không phải chuỗi: {label!r}")
    kind = raw.get("type")
    if kind not in _KINDS:
        raise StrictParseError(f"{path}: type không hợp lệ: {kind!r}")
    children_raw = raw.get("children", [])
    if children_raw in (None, ""):
        children_raw = []
    if not isinstance(children_raw, list):
        raise StrictParseError(f"{path}: children phải là list, gặp {type(children_raw).__name__}")
    if kind == DATA and children_raw:
        raise StrictParseError(f"{path}: node data là lá, không được có con (§3)")
    children = tuple(_node_strict(c, f"{path}.children[{i}]")
                     for i, c in enumerate(children_raw))
    return TreeNode(label=label.strip(), kind=kind, children=children)


# ── Serialization CHO MODEL: space-pad + đổi tên key để tokenizer round-trip ─
# BARTpho-syllable (sentencepiece tiếng Việt) tokenize chữ DÍNH dấu `"` (JSON nén) rất tệ:
# "individual"→"al"; nhãn tiếng Việt vỡ vụn ("Quản"→Qu+ả+n). Thêm KHOẢNG TRẮNG quanh mọi `"` ở
# đường-biên model → tokenize tự nhiên như lúc pretrain ("▁Quản" 1 token, "▁individual" sạch) → model
# SINH nhãn chuẩn hơn. NGOẠI LỆ: "entities" khi pad → `<unk>` (enti vỡ) nên đổi tên thành "items"
# (1 token sạch `▁items`). Thêm `normalize_tone` (nắn dấu kiểu-mới: thủy→thuỷ) → round-trip 97%→100%.
# Nội bộ + ontology + oracle + DATASET VẪN "entities"/individual/object/data; chỉ chuỗi MODEL thấy/sinh
# là dạng pad + "items" + dấu-kiểu-mới. (kiểm thực nghiệm 2026-06-19 — xem PROGRESS.md.)
_QUOTE_PAD = re.compile(r'"')
_QUOTE_UNPAD = re.compile(r'\s*"\s*')


def _rename_key(obj: object, old: str, new: str) -> object:
    """Đệ quy đổi TÊN KEY ``old``→``new`` trong dict (giá trị giữ nguyên)."""
    if isinstance(obj, list):
        return [_rename_key(x, old, new) for x in obj]
    if not isinstance(obj, dict):
        return obj
    return {(new if k == old else k): _rename_key(v, old, new) for k, v in obj.items()}


def to_model_json(tree_dict: dict) -> str:
    """Cây dict → chuỗi JSON CHO MODEL: đổi ``entities``→``items``, nén, **nắn dấu** kiểu-mới (đồng bộ
    ``clean`` ở source), rồi **space-pad** quanh mọi `"`. Dùng làm TARGET train; ``from_model_json``
    đảo ngược lúc infer. Nắn dấu chỉ đổi vị-trí dấu (thủy→thuỷ) cho tokenizer — khớp ontology bỏ dấu nên không ảnh hưởng."""
    compact = json.dumps(_rename_key(tree_dict, "entities", "items"),
                         ensure_ascii=False, separators=(",", ":"))
    return _QUOTE_PAD.sub(' " ', normalize_tone(compact))


def from_model_json(s: str) -> dict:
    """Chuỗi MODEL sinh (pad + "items") → dict cây chuẩn: bỏ khoảng trắng quanh `"`, ``json.loads``,
    đổi ``items``→``entities``. RAISE ``json.JSONDecodeError`` nếu JSON hỏng (caller khoan dung)."""
    return _rename_key(json.loads(_QUOTE_UNPAD.sub('"', s)), "items", "entities")


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
