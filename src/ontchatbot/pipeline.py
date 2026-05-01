"""End-to-end answer pipeline: user query → reply.

Stages
------
1. Greeting detection — keyword heuristic on the diacritic-stripped query.
2. NER inference — PhoBERT extracts ontology entity spans.
3. Fuzzy disambiguation — each span is resolved to its highest-scoring
   individual within the predicted class (skipped if below threshold).
4. SPARQL fetch — per-class fetcher returns a structured record.
5. Compose — greeting first if present, then per-entity rendered blocks; a
   greeting alone or no recognised entity falls back to OOD.
"""

from __future__ import annotations

from .config import GREETING_KEYWORDS
from .data.templates import strip_diacritics
from .ner.inference import extract_entities
from .ontology.fuzzy import FuzzyMatch, best
from .ontology.response import compose, render_blocks


def _detect_greeting(text: str) -> bool:
    norm = strip_diacritics(text.lower()).strip()
    return any(kw in norm for kw in GREETING_KEYWORDS)


def answer(query: str) -> dict:
    """Process a single user query and return ``{reply, greeting, entities}``."""
    text = (query or "").strip()
    if not text:
        return {"reply": compose("", greeting=True, has_entities=False),
                "greeting": True, "entities": []}

    greeting = _detect_greeting(text)
    entities = extract_entities(text)

    matched: list[tuple[str, FuzzyMatch]] = []
    debug: list[dict] = []
    for ent in entities:
        m = best(ent.surface, ent.tag)
        if m:
            matched.append((ent.tag, m))
            debug.append({"surface": ent.surface, "tag": ent.tag,
                          "iri": m.iri, "score": m.score})

    blocks = render_blocks(matched)
    reply = compose(blocks, greeting=greeting, has_entities=bool(matched))
    return {"reply": reply, "greeting": greeting, "entities": debug}
