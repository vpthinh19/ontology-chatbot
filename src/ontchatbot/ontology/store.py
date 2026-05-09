"""The :class:`Ontology` repository: load, introspect, match, describe.

Single point of contact with ``owlready2``. Every other layer of the
chatbot — the renderer, the pipeline, the NER schema accessors — speaks to
ontology data exclusively through dict objects produced here. Swapping the
backing store (a SPARQL endpoint, a Neo4j knowledge graph, …) is therefore
a one-class change.

JSON contract emitted by :meth:`describe` and :meth:`list_class`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The output is *self-describing*: section headers in chat replies are the
Vietnamese ``rdfs:label`` of each property, used **as keys** in the dict.
Adding a new property in Protégé and giving it a Vietnamese label is the
only change required — no Python edit, no schema update.

Four keys are fixed identity metadata (``type``, ``iri``, ``class``,
``label``); every other key is a property label.

Top-level entity (``depth=1``)::

    {
      "type": "individual",
      "iri": "QuyTrinh_NopHocPhi",
      "class": "AcademicProcedure",
      "label": "Quy trình đóng học phí",
      "Mô tả quy trình": "Sinh viên thanh toán...",     # data scalar
      "Được xử lý bởi": [                                # object → list of nested
          {"type": "individual", "iri": "PhongKHTC",
           "class": "AdministrativeOffice",
           "label": "Phòng Tài chính",
           "Website": "https://phongkhtc.ntu.edu.vn/"}   # depth=0 only
      ],
      "Mức học phí/1 Tín chỉ (VNĐ)": 550000,
      ...
    }

Object-property targets (``depth=0``) carry only identity + URL-shaped
data values — Renderer uses the first such value as the markdown link
target.

Class listing::

    {
      "type": "listing",
      "class": "AcademicProcedure",
      "label": "Quy trình học vụ",
      "items": [{"type": "individual", "iri": "...",
                 "class": "...", "label": "..."}]
    }
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import owlready2
from owlready2 import default_world
from rapidfuzz import fuzz, process

from ..core.config import (
    FUZZY_MIN_SCORE,
    FUZZY_TOP_K,
    LABEL_MAP_PATH,
    ONTOLOGY_PATH,
    RENDER_PARAGRAPH_PROPERTIES,
    RENDER_PROPERTY_ORDER,
    RENDER_SKIP_PROPERTIES,
)

log = logging.getLogger(__name__)


# Fixed keys in every JSON dict — Renderer skips them when iterating
# property-label keys. Exported so Renderer can import the same constant.
FIXED_KEYS: frozenset[str] = frozenset({"type", "iri", "class", "label"})

_CAMEL_RE = re.compile(r"([a-z])([A-Z])")
_RE_NONALNUM = re.compile(r"[^\w\s]+")
_RE_WS = re.compile(r"\s+")
_PROP_RANK = {name: i for i, name in enumerate(RENDER_PROPERTY_ORDER)}
_BIG_RANK = len(_PROP_RANK)


def _humanise(local: str) -> str:
    """``DonXinBaoLuu`` → ``Don Xin Bao Luu`` — used as a label fallback."""
    return _CAMEL_RE.sub(r"\1 \2", local.replace("_", " ")).strip()


def _normalize(text: str) -> str:
    """Diacritic-insensitive, lower-case, alphanumeric-only normalisation
    for the fuzzy index. Independent of :class:`Preprocessor` so the
    ontology layer can be exercised without the NER preprocessing chain."""
    nfkd = unicodedata.normalize("NFD", text.lower())
    no_diac = "".join(c for c in nfkd if not unicodedata.combining(c))
    no_diac = no_diac.replace("đ", "d").replace("Đ", "d")
    return _RE_WS.sub(" ", _RE_NONALNUM.sub(" ", no_diac)).strip()


# Match results

@dataclass(frozen=True)
class MatchResult:
    """Outcome of resolving one span against the ontology.

    ``class_won`` and ``individuals`` are mutually informative: when the
    class label wins, ``individuals`` is left empty and the renderer is
    expected to fall back to a class-listing template; otherwise every
    IRI scoring at or above the threshold is included.
    """
    tag: str
    class_won: bool
    individuals: list[str] = field(default_factory=list)
    top_score: float = 0.0


@dataclass(frozen=True)
class _Cand:
    """Internal index entry."""
    iri: str            # ``""`` if this row is the class itself
    norm: str
    is_class: bool


# Ontology repository

class Ontology:
    """OWL world + label-map + fuzzy index, all behind one façade.

    Construction is idempotent and process-cheap (parsing the OWX file is
    the dominant cost), but expensive enough that callers should reuse the
    singleton via :meth:`get` rather than constructing fresh instances.
    """

    def __init__(self,
                 ontology_path: Path = ONTOLOGY_PATH,
                 label_map_path: Path = LABEL_MAP_PATH,
                 *,
                 min_score: float = FUZZY_MIN_SCORE,
                 top_k: int = FUZZY_TOP_K) -> None:
        self._owl = default_world.get_ontology(str(ontology_path)).load()
        # ``label_map.json`` is authored as a list of single-key dicts so
        # tag declaration order is preserved by the JSON spec; flatten it
        # once at load time and forget about that quirk afterwards.
        raw = json.loads(Path(label_map_path).read_text(encoding="utf-8"))
        self._label_map: dict[str, dict] = {}
        for item in raw:
            self._label_map.update(item)
        self._min_score = float(min_score)
        self._top_k = int(top_k)
        log.info("[Ontology] loaded path=%s tags=%d classes=%d individuals=%d",
                 ontology_path, len(self.tags),
                 len(list(self._owl.classes())),
                 len(list(self._owl.individuals())))

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Ontology":
        return cls()

    # NER schema accessors

    @property
    def tags(self) -> list[str]:
        return [k for k, v in self._label_map.items()
                if v.get("type") == "ontology"]

    def bio_labels(self) -> list[str]:
        out = ["O"]
        for tag in self.tags:
            out.extend([f"B-{tag}", f"I-{tag}"])
        return out

    def class_local(self, tag: str) -> str:
        uri = self._label_map.get(tag, {}).get("uri", "")
        return uri.rsplit("#", 1)[-1] if "#" in uri else uri

    # Fuzzy match + score (formerly FuzzyMatcher)

    @lru_cache(maxsize=None)
    def _fuzzy_index(self, tag: str) -> tuple[_Cand, ...]:
        """Build the per-tag search index — class label + individual surfaces.

        Including the class label here makes the matcher *two-mode* in a
        uniform way: the same RapidFuzz call decides whether the user asked
        a class-level question (listing) or pointed at specific individuals
        (description).
        """
        out: list[_Cand] = []
        cls_local = self.class_local(tag)
        cls = self._owl[cls_local]
        if cls is not None:
            for v in (getattr(cls, "label", None) or []):
                n = _normalize(str(v))
                if n:
                    out.append(_Cand(iri="", norm=n, is_class=True))
        for ind in self._individuals_of_class(cls_local):
            iri = ind.name
            forms: set[str] = {iri.replace("_", " ")}
            forms.update(str(v) for v in (getattr(ind, "label", None) or []))
            forms.update(str(v) for v in (getattr(ind, "hasAlias", None) or []))
            for s in forms:
                n = _normalize(s)
                if n:
                    out.append(_Cand(iri=iri, norm=n, is_class=False))
        return tuple(out)

    def resolve(self, span: str, tag: str) -> MatchResult:
        """Two-mode fuzzy resolution.

        * **Class wins** — the class label tied or beat every individual at
          the threshold; downstream renders the listing template.
        * **Individuals win** — every IRI scoring at or above the threshold
          is collected, fixing the historical top-1 collapse on ambiguous
          cohort spans like ``"k65"`` (which legitimately matches *two*
          fees).
        """
        index = self._fuzzy_index(tag)
        q = _normalize(span)
        if not (index and q):
            log.info("[Ontology.resolve] miss surface=%r tag=%s", span, tag)
            return MatchResult(tag=tag, class_won=False)

        raw = process.extract(
            q, {i: e.norm for i, e in enumerate(index)},
            scorer=fuzz.token_set_ratio, limit=self._top_k * 4,
        )
        # Dedupe by entity (each individual contributes many surface forms).
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

    def describe(self, iri: str, depth: int = 1) -> dict | None:
        """Render an individual to the JSON contract documented in module docstring.

        ``depth=1`` (default) produces the full description used at the top
        of a chat reply. ``depth=0`` produces a minimal target dict suitable
        for inclusion as an object-property item — only identity + URL-shaped
        data values are carried, so the renderer can pick the first URL and
        emit a markdown link to the target's label without recursing
        further.
        """
        ind = self._owl[iri]
        if ind is None:
            log.warning("[Ontology.describe] miss iri=%s", iri)
            return None

        cls_local = self._class_local_of(ind)
        out: dict = {
            "type": "individual",
            "iri": ind.name,
            "class": cls_local,
            "label": self._label_of(ind),
        }

        # Order asserted properties stably so reply layout is deterministic
        # whether the schema has 5 or 50 properties; unknown property names
        # are appended alphabetically by their Vietnamese label.
        ordered = sorted(
            self._asserted_properties(ind),
            key=lambda kv: (_PROP_RANK.get(kv[0].name, _BIG_RANK),
                            self._property_label(kv[0])),
        )

        for prop, values in ordered:
            if prop.name in RENDER_SKIP_PROPERTIES:
                continue
            header = self._property_label(prop)
            value = self._render_property_value(prop, values, depth=depth)
            if value in (None, "", []):
                continue
            # depth=0 strips non-URL data values to keep target dicts small.
            if depth == 0 and not _is_url_value(value):
                continue
            out[header] = value
        return out

    def list_class(self, tag: str) -> dict:
        """Class-listing JSON: every individual under the class, label only."""
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
        return {
            "type": "listing",
            "class": cls_local,
            "label": label,
            "items": items,
        }

    # Internals

    def _individuals_of_class(self, cls_local: str) -> list:
        cls = self._owl[cls_local]
        return list(cls.instances()) if cls is not None else []

    def _class_local_of(self, ind) -> str:
        """Return the local name of the *most specific* class of ``ind``.

        Falls back to ``"NamedIndividual"`` if the individual has no
        asserted type (defensive — shouldn't happen with the curated
        ontology, but a graceful default avoids KeyError downstream).
        """
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

    def _render_property_value(self, prop, values: list, *, depth: int):
        """Convert a list of values into the JSON-serialisable form.

        * Object property → list of recursive dicts at ``depth - 1``;
        * paragraph property → joined string preserving authored line breaks;
        * data property scalar → primitive (single value) or list (multiple).
        """
        if isinstance(prop, owlready2.ObjectPropertyClass):
            if depth <= 0:
                return None  # stop recursing at depth 0
            nested: list[dict] = []
            for v in values:
                d = self.describe(v.name, depth=depth - 1)
                if d:
                    nested.append(d)
            return nested or None

        if prop.name in RENDER_PARAGRAPH_PROPERTIES:
            # Convention: paragraph values always carry a leading newline so
            # the renderer can distinguish "free-flow paragraph" (no bullet)
            # from "single-value bullet" without consulting any per-property
            # config. A single-line description like
            # ``"Sinh viên thanh toán..."`` would otherwise look identical
            # to a normal scalar; the leading ``\n`` is the marker.
            return "\n" + "\n".join(_format_scalar(v).strip() for v in values)

        rendered = [_format_scalar(v) for v in values]
        if not rendered:
            return None
        return rendered[0] if len(rendered) == 1 else rendered


# Helpers — kept module-private; Renderer mirrors them locally so the two
# layers don't share imports.

def _format_scalar(v) -> object:
    """Lightly typecast literal values to display-friendly Python primitives."""
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return int(v)
    return str(v)


def _is_url_value(v) -> bool:
    if isinstance(v, str):
        return v.startswith(("http://", "https://"))
    if isinstance(v, list):
        return any(_is_url_value(x) for x in v)
    return False
