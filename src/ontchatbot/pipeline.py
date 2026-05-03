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

Each stage emits a structured log record so a single ``grep`` over
``logs/chatbot.log`` reproduces the data shape as a query traverses the
pipeline.
"""

from __future__ import annotations

import logging

from .config import GREETING_KEYWORDS
from .data.templates import strip_diacritics
from .ner.inference import Entity, extract_entities
from .ontology.fuzzy import FuzzyMatch, best, search
from .ontology.response import compose, render_blocks

log = logging.getLogger(__name__)


def _is_greeting(text: str) -> bool:
    norm = strip_diacritics(text.lower()).strip()
    hit = any(kw in norm for kw in GREETING_KEYWORDS)
    log.debug("[greeting] text=%r normalised=%r hit=%s", text, norm, hit)
    return hit


def _disambiguate(spans: list[Entity]) -> list[tuple[str, FuzzyMatch]]:
    """Resolve every recognised span to its best ontology individual."""
    out: list[tuple[str, FuzzyMatch]] = []
    for ent in spans:
        candidates = search(ent.surface, ent.tag, top_k=3)
        log.info(
            "[fuzzy] surface=%r tag=%s candidates=%s",
            ent.surface, ent.tag,
            [(c.iri, round(c.score, 2)) for c in candidates],
        )
        m = best(ent.surface, ent.tag)
        if m is None:
            log.info("[fuzzy] reject surface=%r tag=%s (below threshold)",
                     ent.surface, ent.tag)
            continue
        out.append((ent.tag, m))
        log.info("[fuzzy] pick surface=%r tag=%s -> iri=%s score=%.2f",
                 ent.surface, ent.tag, m.iri, m.score)
    return out


def answer(query: str) -> dict:
    """Process a single user query and return ``{reply, greeting, entities}``."""
    log.info("[recv] message=%r length=%d", query, len(query or ""))

    text = (query or "").strip()
    if not text:
        log.info("[skip] empty input -> greeting reply")
        return {"reply": compose("", greeting=True), "greeting": True, "entities": []}

    greeting = _is_greeting(text)
    spans = extract_entities(text)
    log.info("[ner] extracted=%d spans=%s", len(spans),
             [{"surface": e.surface, "tag": e.tag,
               "start": e.start, "end": e.end} for e in spans])

    matched = _disambiguate(spans)
    blocks = render_blocks(matched)
    reply = compose(blocks, greeting=greeting)
    log.info("[compose] greeting=%s n_matched=%d block_chars=%d reply_chars=%d",
             greeting, len(matched), len(blocks), len(reply))
    return {
        "reply": reply,
        "greeting": greeting,
        "entities": [
            {"surface": ent.surface, "tag": tag, "iri": m.iri, "score": m.score}
            for ent, (tag, m) in zip(spans, matched)
        ],
    }
