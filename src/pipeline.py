"""End-to-end inference pipeline: user query → reply.

Stages:
    1. Greeting detection — keyword heuristic on the diacritic-stripped query.
    2. NER inference — PhoBERT extracts ontology entity spans.
    3. Fuzzy disambiguation — each span is resolved to the most likely
       individual within its predicted class.
    4. Ontology lookup + rendering — SPARQL fetches per-class fields and the
       response renderer concatenates the per-entity blocks.
    5. Out-of-domain fallback — triggered when neither greeting nor any
       sufficiently confident entity match is found.
"""

from __future__ import annotations

from .config import INTENT_GREETING_KEYWORDS
from .data.templates import strip_diacritics
from .ner.inference import extract_entities
from .ontology.fuzzy import best_match
from .ontology.response import greeting_reply, out_of_domain_reply, render_many


def _is_greeting(text: str) -> bool:
    norm = strip_diacritics(text.lower()).strip()
    return any(kw in norm for kw in INTENT_GREETING_KEYWORDS)


def answer(query: str) -> dict:
    """Process a single user query and return a structured response.

    Returns a dict with ``reply`` (string for the UI), ``intent`` (one of
    ``greeting``/``ontology``/``out_of_domain``), and ``entities`` (the
    list of disambiguated matches, useful for debugging).
    """
    text = (query or "").strip()
    if not text:
        return {"reply": greeting_reply(), "intent": "greeting", "entities": []}

    if _is_greeting(text):
        return {"reply": greeting_reply(), "intent": "greeting", "entities": []}

    entities = extract_entities(text)
    matches = []
    for ent in entities:
        m = best_match(ent.surface, ent.tag)
        if m:
            matches.append((ent.tag, m))

    if not matches:
        return {"reply": out_of_domain_reply(), "intent": "out_of_domain", "entities": []}

    return {
        "reply": render_many(matches),
        "intent": "ontology",
        "entities": [
            {"surface": ent.surface, "tag": ent.tag,
             "iri": m.iri, "score": m.score}
            for ent, (_, m) in zip(entities, matches)
        ],
    }
