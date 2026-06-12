"""Ontology graph: schema (TBox) as a query-planning space + ABox traversal.

This is the research core. The TBox — every object property's *domain* and
*range* — forms a small graph between **classes**. A query is planned by BFS
over that class graph from a constraint's class to the subject (target) class;
the resulting path (each edge tagged forward/inverse) is then *executed* over
individuals. Adding a class or relation in Protégé extends the plan space
with zero code change — the property no SQL JOIN nor similarity score can
express.

The TBox can still be sparse (``thucHienQua``/``coBuoc`` carry zero
assertions even in v9), so domain/range are inferred from **TBox ∪ ABox** at
load and the class graph has no holes. Inverse traversal is *synthesised* from
domain/range here rather than declared as ``owl:inverseOf`` in the ontology —
an undeclared-but-unasserted inverse property would make a forward ``walk``
read an empty relation, so the planner owning both directions is both safer
and the cleaner statement of the research claim.

The third public surface is :meth:`lexicon` — the *danh bạ*: every normalised
surface form in the ontology, each row marked ``class`` (a subject mention)
or ``individual`` (a constraint mention). The baseline NLU scans text against
it with exact whole-phrase matching; the trained NER replaces the scanning,
never the rows (linking still resolves a tagged span through them). The old
fuzzy WRatio matcher and its magic threshold are gone — exact matching is the
honest baseline, contextual robustness is the model's job (step 3).
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from owlready2 import default_world

from .config import ONTOLOGY_PATH
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
class LexEntry:
    """One danh-bạ row: a normalised surface phrase and what it denotes.
    ``kind='class'`` rows become SUBJECT mentions, ``kind='individual'`` rows
    become CONSTRAINT mentions (see nlu)."""
    phrase: str          # normalised (diacritic-stripped) whole phrase
    kind: str            # "class" | "individual"
    cls: str             # owning class local name
    iri: str             # individual iri; "" for class rows


class Graph:
    """OWL world + class-graph schema + lexicon; singleton via ``get()``."""

    def __init__(self, ontology_path: Path = ONTOLOGY_PATH) -> None:
        self._owl = default_world.get_ontology(str(ontology_path)).load()
        self._obj_props: set[str] = {p.name for p in self._owl.object_properties()}
        self._adjacency = self._build_schema()
        self._reverse = self._build_reverse_index()
        self._lexicon = self._build_lexicon()
        log.info("[Graph] loaded classes=%d individuals=%d obj_props=%d "
                 "edges=%d lexicon=%d",
                 len(list(self._owl.classes())),
                 len(list(self._owl.individuals())),
                 len(self._obj_props),
                 sum(len(v) for v in self._adjacency.values()),
                 len(self._lexicon))

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Graph":
        return cls()

    # Schema — class graph from TBox ∪ ABox

    def _build_schema(self) -> dict[str, list[tuple[str, Step]]]:
        """Class adjacency: for each object property, connect every (domain,
        range) class pair with a forward edge and a matching inverse edge.

        Domain/range are taken from the declared TBox and *augmented* with
        classes actually observed in assertions, so schema gaps are filled.
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

    # Traversal

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

    def instances(self, cls: str) -> list[Node]:
        """Every individual of ``cls`` (label-sorted) — class listing."""
        owl_cls = self._owl[cls]
        if owl_cls is None:
            return []
        nodes = [self._node(i.name) for i in owl_cls.instances()]
        return sorted(nodes, key=lambda n: n.label.casefold())

    # Lexicon — the danh bạ the NLU scans / links against

    def lexicon(self) -> tuple[LexEntry, ...]:
        return self._lexicon

    def _build_lexicon(self) -> tuple[LexEntry, ...]:
        """One row per surface form. Class rows come from every ``rdfs:label``
        of every class (the v9 migration adds alias labels such as "học phí");
        individual rows from labels + ``tenGoiKhac`` + IRI words. Exact,
        normalised, whole-phrase — no fuzzy scoring, no threshold."""
        rows: list[LexEntry] = []
        for cls in self._owl.classes():
            for v in (getattr(cls, "label", None) or []):
                n = normalize_for_match(str(v))
                if n:
                    rows.append(LexEntry(n, "class", cls.name, ""))
        for ind in self._owl.individuals():
            cls = self._class_of(ind)
            forms = {ind.name.replace("_", " ")}
            forms.update(str(v) for v in (getattr(ind, "label", None) or []))
            forms.update(str(v) for v in (getattr(ind, "tenGoiKhac", None) or []))
            for s in forms:
                n = normalize_for_match(s)
                if n:
                    rows.append(LexEntry(n, "individual", cls, ind.name))
        return tuple(rows)

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
            if p.name in self._obj_props or p.name in ("label", "tenGoiKhac"):
                continue
            vals = list(p[ind])
            if vals:
                out[p.name] = vals[0] if len(vals) == 1 else list(vals)
        return out

    # Schema accessors

    def class_label(self, cls: str) -> str:
        owl_cls = self._owl[cls]
        labels = list(getattr(owl_cls, "label", []) or []) if owl_cls is not None else []
        return str(labels[0]) if labels else cls

    def property_label(self, prop: str) -> str:
        p = self._owl[prop]
        labels = list(getattr(p, "label", []) or []) if p is not None else []
        return str(labels[0]) if labels else prop

    # Internals

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
