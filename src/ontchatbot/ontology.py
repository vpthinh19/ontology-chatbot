"""Ontology: nạp owl + khớp theo type + thuật toán duyệt (DESIGN.md §5).

Tầng này **chỉ tra thông tin** trên ontology theo đúng cây model đưa — không suy luận,
không planner, không liệt kê lớp. Hai việc:

* :meth:`resolve` (khớp theo ``kind``): individual → khớp tên/alias cá thể (chứa-token,
  điểm cao nhất KHÔNG ngưỡng); object → khớp nhãn object-property; data → khớp nhãn
  datatype-property.
* :meth:`traverse`: đi theo cây, giữ một **"tập hiện tại"** các cá thể (§5). Cha→con = VÀ
  (lọc dần theo chuỗi lồng nhau); anh em cùng cha = nhánh độc lập → gộp.

Chỉ duyệt **xuôi** (theo chiều hub đi ra). Duyệt ngược (§6.8) chưa làm.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from owlready2 import World

from .config import ONTOLOGY_PATH
from .preprocess import normalize_for_match
from .tree import DATA, INDIVIDUAL, OBJECT, QUERY, Tree, TreeNode

log = logging.getLogger(__name__)

_ALIAS_PROP = "tenGoiKhac"          # data-prop chứa alias cá thể (không phải con tra cứu)
_CAMEL_SPLIT = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])")
_ROOT_MARGIN = 10.0                 # class/property phải hơn cá thể margin này mới ép vague


@dataclass(frozen=True)
class OntNode:
    """Một cá thể ontology đã phẳng hoá cho render/eval."""
    iri: str
    cls: str
    label: str
    data: dict = field(default_factory=dict)   # data-prop local-name → giá trị (bỏ alias)


@dataclass(frozen=True)
class DataValue:
    """Một lá ``data``: giá trị của một datatype-property trên tập hiện tại."""
    prop: str          # local name (vd "email")
    values: tuple      # các giá trị


@dataclass
class Result:
    """Kết quả duyệt một cây: node terminal + lá data + nhãn không khớp được.

    ``vague=True`` = gốc trỏ vào CLASS/quan-hệ chứ không phải cá thể (namespace mismatch,
    §4) → render trả "Không hiểu câu hỏi". Đây là LƯỚI AN TOÀN: bắt cả khi model lỡ sinh
    gốc là tên lớp/nhãn property thay vì cá thể."""
    nodes: list[OntNode] = field(default_factory=list)
    values: list[DataValue] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    vague: bool = False


class Ontology:
    """OWL world + chỉ mục khớp; singleton qua :meth:`get`."""

    def __init__(self, ontology_path: Path = ONTOLOGY_PATH) -> None:
        self._owl = World().get_ontology(
            "file://" + Path(ontology_path).resolve().as_posix()).load()
        self._obj_props = [p.name for p in self._owl.object_properties()]
        self._data_props = [p.name for p in self._owl.data_properties()]
        # nhãn-khớp (đã chuẩn hoá) cho từng property
        self._obj_labels = {p: self._norm_labels(p) for p in self._obj_props}
        self._data_labels = {p: self._norm_labels(p)
                             for p in self._data_props if p != _ALIAS_PROP}
        self._class_labels = {c.name: self._norm_labels(c.name) for c in self._owl.classes()}
        # bề mặt khớp (đã chuẩn hoá) cho từng cá thể: tên(camel) + label + alias
        self._forms = {ind.name: self._surface_forms(ind)
                       for ind in self._owl.individuals()}
        log.info("[Ontology] classes=%d individuals=%d obj=%d data=%d",
                 len(list(self._owl.classes())), len(self._forms),
                 len(self._obj_props), len(self._data_props))

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Ontology":
        return cls()

    # ── Khớp (resolve theo kind) ─────────────────────────────────────────────

    def resolve(self, label: str, kind: str) -> list[str] | str | None:
        """individual → list IRI khớp; object/data → tên property; None nếu trượt."""
        if kind == INDIVIDUAL:
            return self._match_individuals(label, self._forms.keys())
        index = self._obj_labels if kind == OBJECT else self._data_labels
        return self._best_property(label, index)

    def _match_individuals(self, label: str, iris) -> list[str]:
        """Cho điểm mọi IRI trong ``iris`` theo nhãn; giữ nhóm điểm cao nhất (>0)."""
        q = normalize_for_match(label)
        scored = [(iri, _score(q, self._forms[iri])) for iri in iris]
        top = max((s for _, s in scored), default=0.0)
        return [iri for iri, s in scored if s == top and s > 0.0] if top > 0.0 else []

    def _best_property(self, label: str, index: dict[str, list[str]]) -> str | None:
        q = normalize_for_match(label)
        best, best_score = None, 0.0
        for prop, labels in index.items():
            s = _score(q, labels)
            if s > best_score:
                best, best_score = prop, s
        return best

    def _root_resolve(self, label: str) -> tuple[str, list[str]]:
        """Khớp GỐC có kiểm namespace (type-safety, không phải luật nghiệp vụ).

        Gốc theo hợp đồng phải là **cá thể**. Nếu label khớp tên CLASS / nhãn PROPERTY rõ
        hơn cá thể ⇒ model sinh sai category ⇒ trả ``vague`` thay vì khớp-một-phần ra rác.
        Trả ``("ok", iris) | ("vague", []) | ("miss", [])``.

        Quy tắc (conservative, theo gợi ý Codex):
        - cá thể exact (=100) thắng cả khi class/property cũng 100 (label lưỡng tính như
          "học phí": ở GỐC phải là cá thể quy trình).
        - class/property exact mà cá thể không exact → vague (namespace mismatch).
        - class/property cao (≥90) hơn cá thể một margin → vague.
        - cá thể đủ chắc (≥80: exact/đủ-token/chuỗi-con) → ok; BỎ "trùng-một-phần" thấp ở gốc.
        """
        q = normalize_for_match(label)
        if not q:
            return ("miss", [])
        i_score, iris = self._score_individuals(q)
        if i_score >= 100.0:
            return ("ok", iris)
        s = max(self._best_label_score(q, self._class_labels.values()),
                self._best_label_score(q, self._obj_labels.values()),
                self._best_label_score(q, self._data_labels.values()))
        if s >= 100.0:
            return ("vague", [])
        if s >= 90.0 and s >= i_score + _ROOT_MARGIN:
            return ("vague", [])
        if i_score >= 80.0:
            return ("ok", iris)
        return ("miss", [])

    def _score_individuals(self, q: str) -> tuple[float, list[str]]:
        """Điểm cá thể tốt nhất + danh sách IRI đạt điểm đó (q đã chuẩn hoá)."""
        scored = [(iri, _score(q, forms)) for iri, forms in self._forms.items()]
        top = max((s for _, s in scored), default=0.0)
        return top, [iri for iri, s in scored if s == top and s > 0.0]

    @staticmethod
    def _best_label_score(q: str, label_lists) -> float:
        return max((_score(q, labels) for labels in label_lists), default=0.0)

    # ── Thuật toán duyệt (§5) ────────────────────────────────────────────────

    def traverse(self, tree: Tree) -> Result:
        """Đi theo cây → :class:`Result`. act != query → Result rỗng (render lo)."""
        result = Result()
        if tree.act != QUERY or tree.root is None:
            return result
        reason, roots = self._root_resolve(tree.root.label)
        if reason == "vague":
            result.vague = True                    # gốc là class/quan-hệ, không có cá thể (§4)
            return result
        if not roots:
            result.misses.append(tree.root.label)
            return result
        self._descend(tree.root, roots, result)
        # gộp + khử trùng node theo IRI, giữ thứ tự
        seen: set[str] = set()
        result.nodes = [n for n in result.nodes if not (n.iri in seen or seen.add(n.iri))]
        return result

    def _descend(self, node: TreeNode, current: list[str], result: Result) -> None:
        """Tập hiện tại = ``current``. Không con → terminal (gộp node). Có con →
        mỗi con là một nhánh độc lập (anh em = gộp) xuất phát từ ``current``."""
        if not node.children:
            result.nodes.extend(self._node(iri) for iri in current)
            return
        for child in node.children:
            self._step(child, current, result)

    def _step(self, child: TreeNode, current: list[str], result: Result) -> None:
        if child.kind == DATA:
            prop = self._best_property(child.label, self._data_labels)
            if prop is None:
                result.misses.append(child.label)
                return
            vals = tuple(v for iri in current
                         for v in (getattr(self._owl[iri], prop, []) or []))
            if vals:
                result.values.append(DataValue(prop=prop, values=vals))
            else:
                result.misses.append(child.label)
            return

        if child.kind == OBJECT:
            prop = self._best_property(child.label, self._obj_labels)
            if prop is None:
                result.misses.append(child.label)
                return
            nxt = _dedup(t for iri in current for t in self._neighbors(iri, prop))
            if not nxt:
                result.misses.append(child.label)
                return
            self._descend(child, nxt, result)      # con của child lồng vào (VÀ); nếu không có → terminal
            return

        # individual: thu hẹp trong (tập hiện tại ∪ node cách 1 bước object)
        candidates = _dedup(list(current)
                            + [t for iri in current for t in self._obj_neighbors(iri)])
        matched = self._match_individuals(child.label, candidates)
        if not matched:
            result.misses.append(child.label)
            return
        self._descend(child, matched, result)

    # ── Đi cạnh ──────────────────────────────────────────────────────────────

    def _neighbors(self, iri: str, prop: str) -> list[str]:
        ind = self._owl[iri]
        return [v.name for v in (getattr(ind, prop, []) or []) if hasattr(v, "name")]

    def _obj_neighbors(self, iri: str) -> list[str]:
        """Mọi cá thể cách ``iri`` đúng 1 bước theo BẤT KỲ object-property."""
        ind = self._owl[iri]
        out: list[str] = []
        for p in self._obj_props:
            out += [v.name for v in (getattr(ind, p, []) or []) if hasattr(v, "name")]
        return out

    # ── Dựng OntNode + chỉ mục ───────────────────────────────────────────────

    def _node(self, iri: str) -> OntNode:
        ind = self._owl[iri]
        if ind is None:
            return OntNode(iri=iri, cls="", label=iri)
        return OntNode(iri=ind.name, cls=self._class_of(ind),
                       label=self._label_of(ind), data=self._data_of(ind))

    def node(self, iri: str) -> OntNode | None:
        return self._node(iri) if self._owl[iri] is not None else None

    def _data_of(self, ind) -> dict:
        out: dict = {}
        for p in self._data_props:
            if p == _ALIAS_PROP:
                continue
            vals = list(getattr(ind, p, []) or [])
            if vals:
                out[p] = vals[0] if len(vals) == 1 else list(vals)
        return out

    def _surface_forms(self, ind) -> tuple[str, ...]:
        forms = {_CAMEL_SPLIT.sub(" ", ind.name)}
        forms.update(str(v) for v in (getattr(ind, "label", None) or []))
        forms.update(str(v) for v in (getattr(ind, _ALIAS_PROP, None) or []))
        return tuple(sorted({normalize_for_match(f) for f in forms if normalize_for_match(f)}))

    def _norm_labels(self, prop_name: str) -> list[str]:
        p = self._owl[prop_name]
        return [normalize_for_match(str(l)) for l in (getattr(p, "label", None) or [])
                if normalize_for_match(str(l))]

    def _class_of(self, ind) -> str:
        for cls in ind.is_a:
            name = getattr(cls, "name", None)
            if name and name != "NamedIndividual":
                return name
        return "NamedIndividual"

    def _label_of(self, node) -> str:
        labels = list(getattr(node, "label", []) or [])
        return str(labels[0]) if labels else _CAMEL_SPLIT.sub(" ", getattr(node, "name", str(node)))

    def class_label(self, cls: str) -> str:
        owl_cls = self._owl[cls]
        labels = list(getattr(owl_cls, "label", []) or []) if owl_cls is not None else []
        return str(labels[0]) if labels else cls

    def property_label(self, prop: str) -> str:
        p = self._owl[prop]
        labels = list(getattr(p, "label", []) or []) if p is not None else []
        return str(labels[0]) if labels else prop


# ── Cho điểm khớp (chứa-token/alias, KHÔNG ngưỡng cứng) ──────────────────────

def _score(q: str, forms) -> float:
    """Điểm khớp ``q`` (đã chuẩn hoá) với tập ``forms`` (đã chuẩn hoá).

    Khớp đúng cả chuỗi alias ⟶ 100 (alias mạnh thắng); mọi token của q là token con
    của form ⟶ 90; q là chuỗi con ⟶ 80; trùng một phần ⟶ tỉ lệ. Dùng chứa-token nên
    "k65" khớp được mẩu nhỏ trong nhãn dài, không bị fuzzy cả chuỗi kéo điểm xuống.
    """
    if not q:
        return 0.0
    qtoks = q.split()
    best = 0.0
    for f in forms:
        if not f:
            continue
        if q == f:
            return 100.0
        ftoks = set(f.split())
        if all(t in ftoks for t in qtoks):
            best = max(best, 90.0)
        elif q in f:
            best = max(best, 80.0)
        else:
            hit = sum(1 for t in qtoks if t in ftoks)
            if hit:
                best = max(best, 50.0 * hit / len(qtoks))
    return best


def _dedup(items) -> list[str]:
    seen: set[str] = set()
    return [x for x in items if not (x in seen or seen.add(x))]
