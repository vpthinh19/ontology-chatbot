"""Ontology repository: load OWL + fuzzy match + JSON description.

Single point of contact with ``owlready2``. Every other layer reads
ontology data only via dicts produced by :meth:`describe` / :meth:`list_class`.

JSON contract: 4 fixed keys (``type``, ``iri``, ``class``, ``label``);
all other keys are Vietnamese property ``rdfs:label``. Paragraph-property
values carry a leading newline as a marker for the renderer.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import owlready2
from owlready2 import default_world
from rapidfuzz import fuzz, process

from .config import (
    FUZZY_MIN_SCORE,
    FUZZY_TOP_K,
    LABEL_MAP_PATH,
    ONTOLOGY_PATH,
    RENDER_PARAGRAPH_PROPERTIES,
    RENDER_PROPERTY_ORDER,
    RENDER_SKIP_PROPERTIES,
)
from .preprocessor import Preprocessor

log = logging.getLogger(__name__)


# Fixed keys in every entity dict — Renderer skips them when iterating
# property-label keys. Re-exported so Renderer can mirror the constant.
FIXED_KEYS: frozenset[str] = frozenset({"type", "iri", "class", "label"})

_CAMEL_RE = re.compile(r"([a-z])([A-Z])")
_PROP_RANK = {name: i for i, name in enumerate(RENDER_PROPERTY_ORDER)}
_BIG_RANK = len(_PROP_RANK)


def _humanise(local: str) -> str:
    """``DonXinBaoLuu`` → ``Don Xin Bao Luu``."""
    return _CAMEL_RE.sub(r"\1 \2", local.replace("_", " ")).strip()


@dataclass(frozen=True)
class MatchResult:
    """One span resolution. ``class_won`` triggers listing; otherwise
    ``individuals`` are every IRI above the score threshold."""
    tag: str
    class_won: bool
    individuals: list[str] = field(default_factory=list)
    top_score: float = 0.0


@dataclass(frozen=True)
class _Cand:
    """Internal index entry. ``iri=""`` marks the class-label row."""
    iri: str
    norm: str
    is_class: bool


class Ontology:
    """OWL world + label-map + fuzzy index; singleton via ``get()``."""


    def __init__(self,
                 ontology_path: Path = ONTOLOGY_PATH,
                 label_map_path: Path = LABEL_MAP_PATH,
                 *,
                 min_score: float = FUZZY_MIN_SCORE,
                 top_k: int = FUZZY_TOP_K) -> None:
        self._owl = default_world.get_ontology(str(ontology_path)).load()
        # label_map.json is authored as a list of single-key dicts to
        # preserve declaration order. Flatten once and forget.
        raw = json.loads(Path(label_map_path).read_text(encoding="utf-8"))
        self._label_map: dict[str, dict] = {}
        for item in raw:
            self._label_map.update(item)
        self._min_score = float(min_score)
        self._top_k = int(top_k)
        self._pre = Preprocessor.get()
        log.info("[Ontology] loaded path=%s tags=%d classes=%d individuals=%d",
                 ontology_path, len(self.tags),
                 len(list(self._owl.classes())),
                 len(list(self._owl.individuals())))

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Ontology":
        return cls()

    # NER schema

    @property
    def tags(self) -> list[str]:
        """NER tags backed by an ontology class, in declaration order."""
        return [k for k, v in self._label_map.items()
                if v.get("type") == "ontology"]

    def class_local(self, tag: str) -> str:
        uri = self._label_map.get(tag, {}).get("uri", "")
        return uri.rsplit("#", 1)[-1] if "#" in uri else uri

    # Fuzzy match + score

    @lru_cache(maxsize=None)
    def _fuzzy_index(self, tag: str) -> tuple[_Cand, ...]:
        """Index = class label + every individual surface (label/alias/name).

        Putting the class row in the same index gives resolve() its two-mode
        decision in one RapidFuzz call.
        """
        out: list[_Cand] = []
        cls_local = self.class_local(tag)
        cls = self._owl[cls_local]
        if cls is not None:
            for v in (getattr(cls, "label", None) or []):
                n = self._pre.normalize_for_match(str(v))
                if n:
                    out.append(_Cand(iri="", norm=n, is_class=True))
        for ind in self._individuals_of_class(cls_local):
            iri = ind.name
            forms: set[str] = {iri.replace("_", " ")}
            forms.update(str(v) for v in (getattr(ind, "label", None) or []))
            forms.update(str(v) for v in (getattr(ind, "hasAlias", None) or []))
            for s in forms:
                n = self._pre.normalize_for_match(s)
                if n:
                    out.append(_Cand(iri=iri, norm=n, is_class=False))
        return tuple(out)

    def resolve(self, span: str, tag: str) -> MatchResult:
        """Two-mode resolve: class-listing or threshold-collected individuals."""
        index = self._fuzzy_index(tag)
        q = self._pre.normalize_for_match(span)
        if not (index and q):
            log.info("[Ontology.resolve] miss surface=%r tag=%s", span, tag)
            return MatchResult(tag=tag, class_won=False)
        raw = process.extract(
            q, {i: e.norm for i, e in enumerate(index)},
            scorer=fuzz.token_set_ratio, limit=self._top_k * 4,
        )
        # Dedup per entity (each individual contributes many surface forms).
        seen: set[str] = set()
        ranked: list[tuple[_Cand, float]] = []
        for _, score, idx in raw:
            cand = index[idx]
            key = "__class__" if cand.is_class else cand.iri
            if key in seen:
                continue
            seen.add(key)
            ranked.append((cand, float(score)))
            if len(ranked) >= self._top_k:
                break
        if not ranked:
            return MatchResult(tag=tag, class_won=False)
        top_cand, top_score = ranked[0]
        if top_cand.is_class and top_score >= self._min_score:
            log.info("[Ontology.resolve] class-win surface=%r tag=%s score=%.2f",
                     span, tag, top_score)
            return MatchResult(tag=tag, class_won=True, top_score=top_score)
        kept = [c.iri for c, s in ranked
                if not c.is_class and s >= self._min_score]
        if not kept:
            log.info("[Ontology.resolve] reject surface=%r tag=%s top=%.2f (below %.0f)",
                     span, tag, top_score, self._min_score)
            return MatchResult(tag=tag, class_won=False, top_score=top_score)
        log.info("[Ontology.resolve] pick surface=%r tag=%s n=%d top=%.2f iris=%s",
                 span, tag, len(kept), top_score, kept)
        return MatchResult(tag=tag, class_won=False,
                           individuals=kept, top_score=top_score)

    # Description → JSON

    def describe(self, iri: str, depth: int = 1, *,
                 seen_links: frozenset[tuple[str, str]] = frozenset()) -> dict | None:
        """Serialise an individual to JSON.

        ``depth=1`` = full description. ``depth=0`` = minimal target form
        (identity + URL-shaped data only) for nested object-property items.

        ``seen_links`` is a set of ``(prop_name, target_iri)`` pairs already
        asserted by an ancestor in the current describe chain — pairs in
        this set are silently dropped from the current level so duplicate
        relationships do not repeat down the tree (e.g. when both a
        procedure and each of its fee categories link the same regulation).
        """
        ind = self._owl[iri]
        if ind is None:
            log.warning("[Ontology.describe] miss iri=%s", iri)
            return None
        out: dict = {
            "type": "individual",
            "iri": ind.name,
            "class": self._class_local_of(ind),
            "label": self._label_of(ind),
        }
        # Stable property order — paragraphs first, then by RENDER_PROPERTY_ORDER,
        # then alphabetically by Vietnamese label. Adding a property in Protégé
        # never reshuffles existing layout.
        asserted = self._asserted_properties(ind)
        ordered = sorted(
            asserted,
            key=lambda kv: (_PROP_RANK.get(kv[0].name, _BIG_RANK),
                            self._property_label(kv[0])),
        )
        # All outgoing object links from THIS entity — cumulated with the
        # ancestor set and handed to every child describe call so deeper
        # levels can dedup against any link asserted by any ancestor on
        # the chain (not just the immediately preceding property).
        own_links = frozenset(
            (prop.name, target.name)
            for prop, values in asserted
            if isinstance(prop, owlready2.ObjectPropertyClass)
            for target in values
        )
        descendant_seen = seen_links | own_links
        for prop, values in ordered:
            if prop.name in RENDER_SKIP_PROPERTIES:
                continue
            header = self._property_label(prop)
            value = self._render_property_value(
                prop, values, depth=depth,
                ancestor_seen=seen_links,
                descendant_seen=descendant_seen,
            )
            if value in (None, "", []):
                continue
            # depth=0 strips non-URL data so target dicts stay small.
            if depth == 0 and not _has_url(value):
                continue
            out[header] = value
        return out

    def list_class(self, tag: str) -> dict:
        """Class-listing JSON: every individual under the class (label only)."""
        cls_local = self.class_local(tag)
        cls = self._owl[cls_local]
        items: list[dict] = []
        for ind in sorted(self._individuals_of_class(cls_local),
                          key=lambda x: self._label_of(x).casefold()):
            items.append({
                "type": "individual",
                "iri": ind.name,
                "class": cls_local,
                "label": self._label_of(ind),
            })
        label = (str(list(getattr(cls, "label", []) or [])[0])
                 if cls is not None and getattr(cls, "label", None)
                 else self._label_map.get(tag, {}).get("label", tag))
        return {"type": "listing", "class": cls_local,
                "label": label, "items": items}

    # Internals

    def _individuals_of_class(self, cls_local: str) -> list:
        cls = self._owl[cls_local]
        return list(cls.instances()) if cls is not None else []

    def _class_local_of(self, ind) -> str:
        """Most-specific asserted class of ``ind`` (local name)."""
        for cls in ind.is_a:
            name = getattr(cls, "name", None)
            if name and name != "NamedIndividual":
                return name
        return "NamedIndividual"

    def _label_of(self, node) -> str:
        labels = list(getattr(node, "label", []) or [])
        if labels:
            return str(labels[0])
        return _humanise(getattr(node, "name", str(node)))

    def _property_label(self, prop) -> str:
        labels = list(getattr(prop, "label", []) or [])
        return str(labels[0]) if labels else _humanise(prop.name)

    @staticmethod
    def _asserted_properties(individual) -> list[tuple[object, list]]:
        out: list[tuple[object, list]] = []
        for prop in individual.get_properties():
            values = list(prop[individual])
            if values:
                out.append((prop, values))
        return out

    def _render_property_value(self, prop, values: list, *, depth: int,
                               ancestor_seen: frozenset[tuple[str, str]] = frozenset(),
                               descendant_seen: frozenset[tuple[str, str]] = frozenset()):
        """Serialise one property's values: object → nested dicts; paragraph
        → joined string with leading ``\\n``; other → primitive or list.

        ``ancestor_seen`` is the set of ``(prop, target)`` pairs already
        asserted by some ancestor — used to filter values OUT at this
        level. ``descendant_seen`` adds this entity's own outgoing links
        (computed once by the caller) and is what we hand down to nested
        describes so they can dedup against the full ancestor chain.
        """
        if isinstance(prop, owlready2.ObjectPropertyClass):
            if depth <= 0:
                return None
            # Drop targets already asserted on an ancestor under the same
            # predicate — same (predicate, target) pair must not repeat
            # down the tree. Different predicate or different target stays.
            kept = [v for v in values
                    if (prop.name, v.name) not in ancestor_seen]
            if not kept:
                return None
            nested = [d for d in (self.describe(v.name, depth=depth - 1,
                                                seen_links=descendant_seen)
                                  for v in kept) if d]
            return nested or None
        if prop.name in RENDER_PARAGRAPH_PROPERTIES:
            # Leading newline = paragraph marker — works for both single and
            # multi-line content, regardless of language. Renderer keys off
            # this convention rather than per-property config.
            return "\n" + "\n".join(str(v).strip() for v in values)
        # Owlready2 already returns the right Python primitives; no coercion.
        return values[0] if len(values) == 1 else list(values)


def _has_url(v) -> bool:
    """True if ``v`` (or any element if it's a list) is a URL string."""
    if Preprocessor.is_url(v):
        return True
    if isinstance(v, list):
        return any(Preprocessor.is_url(x) for x in v)
    return False
