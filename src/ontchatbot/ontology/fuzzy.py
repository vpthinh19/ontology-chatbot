"""Map an entity surface to a concrete ontology individual via fuzzy matching.

For every NER tag we precompute a search index of surface forms — the
individual's ``rdfs:label`` plus every ``hasAlias`` literal plus the humanised
local name — and rely on RapidFuzz's token-set ratio (robust to reordering and
extra tokens, common in conversational Vietnamese) to recover the canonical
individual even from noisy spans.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz, process

from ..core.config import FUZZY_MIN_SCORE, FUZZY_TOP_K
from .loader import class_local, iter_individuals, load_ontology, short_name


_RE_NONALNUM = re.compile(r"[^\w\s]+")
_RE_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Diacritic-insensitive, lowercase, alphanumeric-only normalisation."""
    nfkd = unicodedata.normalize("NFD", text.lower())
    no_diac = "".join(c for c in nfkd if not unicodedata.combining(c))
    no_diac = no_diac.replace("đ", "d").replace("Đ", "d")
    return _RE_WS.sub(" ", _RE_NONALNUM.sub(" ", no_diac)).strip()


@dataclass(frozen=True)
class _Entry:
    iri: str
    surface: str
    norm: str


@lru_cache(maxsize=None)
def _index(tag: str) -> tuple[_Entry, ...]:
    load_ontology()
    cls_local = class_local(tag)
    out: list[_Entry] = []
    for ind in iter_individuals(cls_local):
        iri = short_name(ind)
        forms: set[str] = {iri.replace("_", " ")}
        for v in getattr(ind, "label", None) or []:
            forms.add(str(v))
        for v in getattr(ind, "hasAlias", None) or []:
            forms.add(str(v))
        for s in forms:
            n = _norm(s)
            if n:
                out.append(_Entry(iri=iri, surface=s, norm=n))
    return tuple(out)


@dataclass(frozen=True)
class FuzzyMatch:
    iri: str
    surface: str
    score: float


def search(span: str, tag: str, top_k: int = FUZZY_TOP_K) -> list[FuzzyMatch]:
    """Return up to ``top_k`` best-matching individuals of ``tag`` for ``span``.

    Results are deduplicated by IRI (the highest-scoring surface form per
    individual is kept).
    """
    index = _index(tag)
    if not index:
        return []
    q = _norm(span)
    if not q:
        return []
    candidates = {i: e.norm for i, e in enumerate(index)}
    raw = process.extract(q, candidates, scorer=fuzz.token_set_ratio,
                          limit=top_k * 4)
    seen: set[str] = set()
    out: list[FuzzyMatch] = []
    for _, score, idx in raw:
        e = index[idx]
        if e.iri in seen:
            continue
        seen.add(e.iri)
        out.append(FuzzyMatch(iri=e.iri, surface=e.surface, score=float(score)))
        if len(out) >= top_k:
            break
    return out


def best(span: str, tag: str) -> FuzzyMatch | None:
    """Top match for the span, or ``None`` if confidence is below threshold."""
    hits = search(span, tag, top_k=1)
    return hits[0] if hits and hits[0].score >= FUZZY_MIN_SCORE else None
