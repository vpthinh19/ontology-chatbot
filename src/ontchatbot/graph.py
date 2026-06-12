"""Ontology graph: schema (TBox) as a query-planning space + ABox traversal.

This is the research core. The TBox — every object property's *domain* and
*range* — forms a small graph between **classes**. A query is planned by BFS
over that class graph from the anchor's class to the intent's target class;
the resulting path (each edge tagged forward/inverse) is then *executed* over
individuals. Adding a class or relation in Protégé extends the plan space
with zero code change — the property no SQL JOIN nor similarity score can
express.

Four traversal primitives replace the old recursive ``describe`` dump:
``anchor`` (resolve text → a *set* of nodes), ``walk`` (run a plan over the
ABox), ``filter_by`` (intersect along a dimension), ``instances`` (listing).

The TBox can still be sparse (``executedVia``/``hasStep`` carry zero
assertions even in v9), so domain/range are inferred from **TBox ∪ ABox** at
load and the class graph has no holes. Inverse traversal is *synthesised* from
domain/range here rather than declared as ``owl:inverseOf`` in the ontology —
an undeclared-but-unasserted inverse property would make a forward ``walk``
read an empty relation, so the planner owning both directions is both safer
and the cleaner statement of the research claim.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import owlready2
from owlready2 import default_world
from rapidfuzz import fuzz, process

from .config import FUZZY_MIN_SCORE, FUZZY_TOP_K, LABEL_MAP_PATH, ONTOLOGY_PATH
from .text import normalize_for_match

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Node:
    """One ontology individual, flattened. Relations are fetched via
    :meth:`Graph.walk`, never embedded — so no recursive dedup is needed."""
    iri: str
    cls: str
    label: str
    data: dict = field(default_factory=dict)  # data-property local-name → value


@dataclass(frozen=True)
class Step:
    """One hop of a plan: traverse ``prop`` forward (domain→range) or
    inverse (range→domain)."""
    prop: str
    inverse: bool

    def __repr__(self) -> str:  # compact plan logging
        return f"{self.prop}{'◂' if self.inverse else '▸'}"


@dataclass(frozen=True)
class Anchor:
    """Result of resolving a surface form. ``class_won`` means the surface
    matched a *class label* (→ listing) rather than any individual."""
    nodes: list[Node]
    cls: str = ""
    class_won: bool = False
    score: float = 0.0
    tag: str = ""


@dataclass(frozen=True)
class _Cand:
    """Internal fuzzy-index entry. ``iri=""`` marks a class-label row."""
    iri: str
    cls: str
    tag: str
    norm: str
    is_class: bool


class Graph:
    """OWL world + class-graph schema + fuzzy index; singleton via ``get()``."""

    def __init__(self,
                 ontology_path: Path = ONTOLOGY_PATH,
                 label_map_path: Path = LABEL_MAP_PATH,
                 *,
                 min_score: float = FUZZY_MIN_SCORE,
                 top_k: int = FUZZY_TOP_K) -> None:
        self._owl = default_world.get_ontology(str(ontology_path)).load()
        raw = json.loads(Path(label_map_path).read_text(encoding="utf-8"))
        self._tag_uri: dict[str, str] = {}
        for item in raw:
            for tag, meta in item.items():
                if meta.get("type") == "ontology":
                    self._tag_uri[tag] = meta["uri"]
        self._cls_tag = {self._local(uri): tag for tag, uri in self._tag_uri.items()}
        self._min_score = float(min_score)
        self._top_k = int(top_k)

        self._obj_props: set[str] = {p.name for p in self._owl.object_properties()}
        self._adjacency = self._build_schema()
        self._reverse = self._build_reverse_index()
        log.info("[Graph] loaded classes=%d individuals=%d obj_props=%d edges=%d",
                 len(list(self._owl.classes())),
                 len(list(self._owl.individuals())),
                 len(self._obj_props),
                 sum(len(v) for v in self._adjacency.values()))

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Graph":
        return cls()

    # Schema — class graph from TBox ∪ ABox

    def _build_schema(self) -> dict[str, list[tuple[str, Step]]]:
        """Class adjacency: for each object property, connect every (domain,
        range) class pair with a forward edge and a matching inverse edge.

        Domain/range are taken from the declared TBox and *augmented* with
        classes actually observed in assertions, so v8's gaps are filled.
        """
        doms: dict[str, set[str]] = {}
        rngs: dict[str, set[str]] = {}
        for p in self._owl.object_properties():
            doms[p.name] = {c.name for c in p.domain if hasattr(c, "name")}
            rngs[p.name] = {c.name for c in p.range if hasattr(c, "name")}
        # ABox augmentation
        for s in self._owl.individuals():
            s_classes = self._classes_of(s)
            for p in s.get_properties():
                if p.name not in self._obj_props:
                    continue
                vals = list(p[s])
                if not vals:
                    continue
                doms.setdefault(p.name, set()).update(s_classes)
                for v in vals:
                    rngs.setdefault(p.name, set()).update(self._classes_of(v))

        adj: dict[str, list[tuple[str, Step]]] = {}
        for prop in self._obj_props:
            for d in doms.get(prop, set()):
                for r in rngs.get(prop, set()):
                    if not d or not r:
                        continue
                    adj.setdefault(d, []).append((r, Step(prop, inverse=False)))
                    adj.setdefault(r, []).append((d, Step(prop, inverse=True)))
        return adj

    def _build_reverse_index(self) -> dict[tuple[str, str], list[str]]:
        """``(prop, target_iri) → [subject_iri, …]`` for O(1) inverse walks."""
        rev: dict[tuple[str, str], list[str]] = {}
        for s in self._owl.individuals():
            for p in s.get_properties():
                if p.name not in self._obj_props:
                    continue
                for v in p[s]:
                    if hasattr(v, "name"):
                        rev.setdefault((p.name, v.name), []).append(s.name)
        return rev

    def plan(self, anchor_cls: str, target_cls: str) -> list[Step] | None:
        """Shortest path of :class:`Step` from ``anchor_cls`` to ``target_cls``.

        ``[]`` when the anchor is already the target (answer = the node's own
        data). ``None`` when the classes are disconnected in the schema.
        BFS guarantees the fewest hops; ties resolve by edge insertion order.
        """
        if anchor_cls == target_cls:
            return []
        seen = {anchor_cls}
        queue: deque[tuple[str, list[Step]]] = deque([(anchor_cls, [])])
        while queue:
            cls, path = queue.popleft()
            for nxt, step in self._adjacency.get(cls, ()):
                if nxt in seen:
                    continue
                new_path = path + [step]
                if nxt == target_cls:
                    return new_path
                seen.add(nxt)
                queue.append((nxt, new_path))
        return None

    # Traversal primitives

    def walk(self, node: Node, steps: list[Step]) -> list[Node]:
        """Execute a plan over the ABox; dedup targets by IRI, keep order."""
        frontier = [node.iri]
        for step in steps:
            nxt: list[str] = []
            for iri in frontier:
                nxt.extend(self._neighbors(iri, step))
            # de-dup preserving order
            frontier = list(dict.fromkeys(nxt))
        return [self._node(iri) for iri in frontier if self._owl[iri] is not None]

    def _neighbors(self, iri: str, step: Step) -> list[str]:
        if step.inverse:
            return list(self._reverse.get((step.prop, iri), ()))
        ind = self._owl[iri]
        if ind is None:
            return []
        prop = getattr(ind, step.prop, None) or []
        return [v.name for v in prop if hasattr(v, "name")]

    def filter_by(self, nodes: list[Node], *,
                  cohort: str = "", program: str = "") -> list[Node]:
        """Intersect a fee set along the v9 structured dimensions.

        ``cohort`` (a code like ``K65``) matches a fee's ``appliesToCohort →
        Khoa.cohortCode``; ``program`` (a ``Nganh`` IRI) matches membership in
        the fee's ``appliesToProgram`` set. Each dimension narrows *only when it
        bites*, so a bare cohort returns the whole cohort (the multi_match
        contract) while cohort ∩ program collapses to the single fee — the set
        arithmetic a top-1 similarity score cannot express.
        """
        out = nodes
        if cohort:
            hit = [n for n in out if self._fee_in_cohort(n.iri, cohort)]
            if hit:
                out = hit
        if program:
            hit = [n for n in out if program in self._fee_programs(n.iri)]
            if hit:
                out = hit
        return out

    def _fee_in_cohort(self, fee_iri: str, code: str) -> bool:
        want = code.casefold()
        for kh in self._neighbors(fee_iri, Step("appliesToCohort", inverse=False)):
            ind = self._owl[kh]
            if any(str(c).casefold() == want
                   for c in (getattr(ind, "cohortCode", None) or [])):
                return True
        return False

    def _fee_programs(self, fee_iri: str) -> set[str]:
        return set(self._neighbors(fee_iri, Step("appliesToProgram", inverse=False)))

    def resolve_program(self, text: str) -> str:
        """Resolve a program (``Nganh``) IRI from free text via label/alias.

        Whole-phrase (space-delimited) match, longest wins — so ``"ngành công
        nghệ thông tin"`` beats the short ``"it"`` alias and a stray ``"it"``
        inside another word never fires. Returns ``""`` on no match. Feeding the
        result to :meth:`filter_by` is what turns ``"học phí K65 ngành CNTT"``
        into a one-node answer."""
        q = normalize_for_match(text)
        cls = self._owl["Nganh"] if q else None
        if cls is None:
            return ""
        padded = f" {q} "
        best, best_len = "", 0
        for ind in cls.instances():
            forms = {str(v) for v in (getattr(ind, "label", None) or [])}
            forms.update(str(v) for v in (getattr(ind, "hasAlias", None) or []))
            for f in forms:
                key = normalize_for_match(f)
                if key and f" {key} " in padded and len(key) > best_len:
                    best, best_len = ind.name, len(key)
        return best

    def instances(self, cls: str) -> list[Node]:
        """Every individual of ``cls`` (label-sorted) — class listing."""
        owl_cls = self._owl[cls]
        if owl_cls is None:
            return []
        nodes = [self._node(i.name) for i in owl_cls.instances()]
        return sorted(nodes, key=lambda n: n.label.casefold())

    # Resolution — text → a *set* of nodes (never argmax-1)

    # How far below the top score a same-class individual may still be
    # collected — keeps the near-tied fee variants of one cohort together
    # while dropping clearly-weaker matches (the multi-office false positives).
    _COLLECT_GAP = 5.0

    def anchor(self, span: str, tag: str = "", *, prefer_cls: str = "") -> Anchor:
        """Resolve a surface form to a node *set* (never argmax-1).

        Two passes. When ``prefer_cls`` is set (the intent implies the anchor's
        class), we first resolve *restricted* to that class; a confident hit
        wins outright. This beats additive biasing because v8's polluted
        aliases (a fee query matching the *procedure* alias ``hoc phi``) can
        out-score the right class by more than any safe margin. On a weak hit
        we fall back to a cross-tag search so multi-class intents (a document
        or procedure both reachable for ASK_OFFICE) still resolve.

        ``tag`` empty → search every NER class (the rule-based baseline has no
        NER to pre-select one).
        """
        q = normalize_for_match(span)
        if not q:
            return Anchor(nodes=[])
        if prefer_cls and prefer_cls in self._cls_tag:
            hit = self._resolve(q, (self._cls_tag[prefer_cls],))
            if hit.nodes or hit.class_won:
                return hit
        tags = (tag,) if tag else tuple(self._tag_uri)
        return self._resolve(q, tags)

    def _resolve(self, q: str, tags: tuple[str, ...]) -> Anchor:
        """Fuzzy-rank ``q`` over ``tags``; class-label win → listing, else a
        gap-bounded set of same-class individuals above threshold."""
        index = self._index(tags)
        if not index:
            return Anchor(nodes=[])
        raw = process.extract(
            q, {i: e.norm for i, e in enumerate(index)},
            scorer=fuzz.WRatio, limit=self._top_k * 6,
        )
        seen: set[str] = set()
        ranked: list[tuple[_Cand, float]] = []
        for _, score, idx in raw:
            cand = index[idx]
            key = f"__class__{cand.cls}" if cand.is_class else cand.iri
            if key in seen:
                continue
            seen.add(key)
            ranked.append((cand, float(score)))
            if len(ranked) >= self._top_k:
                break
        if not ranked:
            return Anchor(nodes=[])
        top_cand, top_score = ranked[0]
        if top_score < self._min_score:
            log.info("[Graph.anchor] reject top=%.1f (<%.0f) tags=%s",
                     top_score, self._min_score, tags)
            return Anchor(nodes=[], score=top_score)
        if top_cand.is_class:
            return Anchor(nodes=[], cls=top_cand.cls, class_won=True,
                          score=top_score, tag=top_cand.tag)
        win_cls = top_cand.cls
        floor = max(self._min_score, top_score - self._COLLECT_GAP)
        kept = [self._node(c.iri) for c, s in ranked
                if not c.is_class and c.cls == win_cls and s >= floor]
        kept = list({n.iri: n for n in kept}.values())
        log.info("[Graph.anchor] cls=%s n=%d top=%.1f floor=%.1f",
                 win_cls, len(kept), top_score, floor)
        return Anchor(nodes=kept, cls=win_cls, score=top_score,
                      tag=self._cls_tag.get(win_cls, ""))

    @lru_cache(maxsize=None)
    def _index(self, tags: tuple[str, ...]) -> tuple[_Cand, ...]:
        """Fuzzy index over the given tags: class label rows + every
        individual surface (IRI words, labels, aliases)."""
        out: list[_Cand] = []
        for tag in tags:
            cls_local = self._local(self._tag_uri[tag])
            cls = self._owl[cls_local]
            if cls is None:
                continue
            for v in (getattr(cls, "label", None) or []):
                n = normalize_for_match(str(v))
                if n:
                    out.append(_Cand("", cls_local, tag, n, True))
            for ind in cls.instances():
                forms = {ind.name.replace("_", " ")}
                forms.update(str(v) for v in (getattr(ind, "label", None) or []))
                forms.update(str(v) for v in (getattr(ind, "hasAlias", None) or []))
                for s in forms:
                    n = normalize_for_match(s)
                    if n:
                        out.append(_Cand(ind.name, cls_local, tag, n, False))
        return tuple(out)

    # Node construction

    def _node(self, iri: str) -> Node:
        ind = self._owl[iri]
        if ind is None:
            return Node(iri=iri, cls="", label=iri)
        return Node(iri=ind.name, cls=self._class_of(ind),
                    label=self._label_of(ind), data=self._data_of(ind))

    def node(self, iri: str) -> Node | None:
        return self._node(iri) if self._owl[iri] is not None else None

    def _data_of(self, ind) -> dict:
        """Data-property values keyed by local name; object links are excluded
        (those are reached via :meth:`walk`)."""
        out: dict = {}
        for p in ind.get_properties():
            if p.name in self._obj_props or p.name in ("label", "hasAlias"):
                continue
            vals = list(p[ind])
            if vals:
                out[p.name] = vals[0] if len(vals) == 1 else list(vals)
        return out

    # Schema accessors (used by the planner / answer layer)

    def class_of_tag(self, tag: str) -> str:
        return self._local(self._tag_uri.get(tag, ""))

    def property_label(self, prop: str) -> str:
        p = self._owl[prop]
        labels = list(getattr(p, "label", []) or []) if p is not None else []
        return str(labels[0]) if labels else prop

    # Internals

    @staticmethod
    def _local(uri: str) -> str:
        return uri.rsplit("#", 1)[-1] if "#" in uri else uri

    @staticmethod
    def _classes_of(node) -> set[str]:
        return {c.name for c in getattr(node, "is_a", [])
                if getattr(c, "name", None) and c.name != "NamedIndividual"}

    def _class_of(self, ind) -> str:
        for cls in ind.is_a:
            name = getattr(cls, "name", None)
            if name and name != "NamedIndividual":
                return name
        return "NamedIndividual"

    def _label_of(self, node) -> str:
        labels = list(getattr(node, "label", []) or [])
        if labels:
            return str(labels[0])
        return getattr(node, "name", str(node)).replace("_", " ")
