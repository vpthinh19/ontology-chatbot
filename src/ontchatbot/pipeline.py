"""End-to-end answer pipeline: user query → reply.

Stages
------
1. **Greeting detection** — keyword heuristic on the diacritic-stripped query.
2. **NER inference** — PhoBERT extracts ontology entity spans.
3. **Fuzzy disambiguation** — each span is mapped to its highest-scoring
   individual within the predicted class (skipped when below threshold).
4. **SPARQL fetch** — per-class fetcher returns a structured record.
5. **Compose** — greeting first if present, then the per-entity rendered
   blocks; falls back to the out-of-domain reply when no entity matches.
"""

from __future__ import annotations

from .config import GREETING_KEYWORDS
from .data.templates import strip_diacritics
from .ner.inference import Entity, extract_entities
from .ontology.fuzzy import FuzzyMatch, best
from .ontology.response import compose, render_blocks


def _is_greeting(text: str) -> bool:
    norm = strip_diacritics(text.lower()).strip()
    return any(kw in norm for kw in GREETING_KEYWORDS)


def _disambiguate(entities: list[Entity]) -> list[tuple[str, FuzzyMatch]]:
    """Resolve every recognised span to its best ontology individual."""
    out: list[tuple[str, FuzzyMatch]] = []
    for ent in entities:
        m = best(ent.surface, ent.tag)
        if m is not None:
            out.append((ent.tag, m))
    return out


def answer(query: str) -> dict:
    """Process a single user query and return ``{reply, greeting, entities}``."""
    text = (query or "").strip()
    if not text:
        return {"reply": compose("", greeting=True), "greeting": True, "entities": []}

    greeting = _is_greeting(text)
    spans = extract_entities(text)
    matched = _disambiguate(spans)
    blocks = render_blocks(matched)
    return {
        "reply": compose(blocks, greeting=greeting),
        "greeting": greeting,
        "entities": [
            {"surface": ent.surface, "tag": tag, "iri": m.iri, "score": m.score}
            for ent, (tag, m) in zip(spans, matched)
        ],
    }
