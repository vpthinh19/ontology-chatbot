"""Fuzzy matching from a recognised entity span to a concrete ontology individual.

For each ontology class we precompute a search index of surface forms — the
individual's local name (humanised), its rdfs:label if any, and every
``hasAlias`` literal — so that approximate string matching with RapidFuzz can
recover the canonical individual even when the user's surface form is noisy
(typos, abbreviations, diacritic loss).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz, process

from ..config import FUZZY_MIN_SCORE, FUZZY_TOP_K
from .loader import iter_individuals, load_ontology, short_iri, tag_to_class_local


_RE_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_RE_NONALNUM = re.compile(r"[^\w\s]")


def _strip_diacritics(text: str) -> str:
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def _humanize(name: str) -> str:
    """Convert a CamelCase / underscore-delimited individual name into prose."""
    name = name.replace("_", " ")
    name = _RE_CAMEL.sub(" ", name)
    return name.strip()


def _normalize(text: str) -> str:
    text = _strip_diacritics(text.lower())
    text = _RE_NONALNUM.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class IndividualEntry:
    """Search-index entry mapping a normalised surface form to its individual."""
    iri: str
    surface: str
    norm: str


@lru_cache(maxsize=None)
def build_index(class_tag: str) -> tuple[IndividualEntry, ...]:
    """Build (and cache) the searchable surface-form index for one NER class.

    Pulls the individual's local name (humanised) plus all ``hasAlias`` values.
    """
    load_ontology()
    cls_local = tag_to_class_local(class_tag)
    entries: list[IndividualEntry] = []
    for ind in iter_individuals(cls_local):
        iri = short_iri(ind)
        surfaces: set[str] = {_humanize(iri)}
        aliases = getattr(ind, "hasAlias", None) or []
        for a in aliases:
            if isinstance(a, str) and a.strip():
                surfaces.add(a.strip())
        # FeeCategory: appliesToTarget literals contain comma-separated programmes
        targets = getattr(ind, "appliesToTarget", None) or []
        for t in targets:
            if isinstance(t, str):
                for piece in t.split(","):
                    p = piece.strip()
                    if p:
                        surfaces.add(p)
        for s in surfaces:
            n = _normalize(s)
            if n:
                entries.append(IndividualEntry(iri=iri, surface=s, norm=n))
    return tuple(entries)


@dataclass(frozen=True)
class FuzzyMatch:
    iri: str
    surface: str
    score: float


def match(span: str, class_tag: str, top_k: int = FUZZY_TOP_K) -> list[FuzzyMatch]:
    """Return top-k individuals of ``class_tag`` ranked by similarity to ``span``.

    Uses token-set ratio as the primary metric (robust to word reordering and
    extraneous tokens, which fits Vietnamese conversational queries).
    """
    index = build_index(class_tag)
    if not index:
        return []
    query = _normalize(span)
    if not query:
        return []
    candidates = {i: e.norm for i, e in enumerate(index)}
    raw = process.extract(
        query, candidates, scorer=fuzz.token_set_ratio, limit=top_k
    )
    out: list[FuzzyMatch] = []
    seen: set[str] = set()
    for _, score, idx in raw:
        e = index[idx]
        if e.iri in seen:
            continue
        seen.add(e.iri)
        out.append(FuzzyMatch(iri=e.iri, surface=e.surface, score=float(score)))
    return out


def best_match(span: str, class_tag: str) -> FuzzyMatch | None:
    """Best individual match if it exceeds the configured confidence threshold."""
    hits = match(span, class_tag, top_k=1)
    if not hits:
        return None
    return hits[0] if hits[0].score >= FUZZY_MIN_SCORE else None
