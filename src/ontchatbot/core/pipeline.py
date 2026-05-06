"""End-to-end answer pipeline: user query → reply.

Architecture
------------
The orchestration is expressed as a *Pipes-and-Filters* chain (a thin variant
of Chain-of-Responsibility). A query is wrapped in a :class:`PipelineContext`
that flows through an ordered list of :class:`Stage` callables; each stage
reads / writes the same context object and returns it. The final stage
produces the user-facing reply.

Benefits
~~~~~~~~
* **Stage isolation** — every stage is a single-responsibility callable that
  can be unit-tested in microseconds (no model load required for most).
* **Stage swappability** — replacing the NER component or adding a
  spell-correction stage is a one-line change to :data:`DEFAULT_STAGES`.
* **Uniform tracing** — :class:`Pipeline` emits a structured log record per
  stage so a single ``grep`` over ``logs/chatbot.log`` reproduces the data
  shape as a query traverses the pipeline.

Stages (in order)
~~~~~~~~~~~~~~~~~
``trim`` → ``greeting`` → ``ner`` → ``fuzzy`` → ``render`` → ``compose``
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from ..data.templates import strip_diacritics
from ..ner.inference import Entity, extract_entities
from ..ontology.fuzzy import FuzzyMatch, best, search
from ..ontology.response import compose, render_blocks
from .config import GREETING_KEYWORDS

log = logging.getLogger(__name__)


# Context

@dataclass
class PipelineContext:
    """The data envelope mutated by every stage.

    Attributes accumulate in the order the stages execute, so a partial
    context is still meaningful for diagnostics if a stage short-circuits.
    """
    query: str
    text: str = ""
    greeting: bool = False
    spans: list[Entity] = field(default_factory=list)
    matches: list[tuple[str, FuzzyMatch]] = field(default_factory=list)
    blocks: str = ""
    reply: str = ""

    def to_response(self) -> dict:
        return {
            "reply": self.reply,
            "greeting": self.greeting,
            "entities": [
                {"surface": ent.surface, "tag": tag,
                 "iri": m.iri, "score": m.score}
                for ent, (tag, m) in zip(self.spans, self.matches)
            ],
        }


# Stage protocol + concrete stages

Stage = Callable[[PipelineContext], PipelineContext]


def trim_stage(ctx: PipelineContext) -> PipelineContext:
    """Strip whitespace; record the cleaned query for downstream stages."""
    ctx.text = (ctx.query or "").strip()
    log.info("[recv] message=%r length=%d", ctx.query, len(ctx.query or ""))
    return ctx


def greeting_stage(ctx: PipelineContext) -> PipelineContext:
    """Diacritic-insensitive keyword match for greetings / closings."""
    if not ctx.text:
        return ctx
    norm = strip_diacritics(ctx.text.lower()).strip()
    ctx.greeting = any(kw in norm for kw in GREETING_KEYWORDS)
    log.debug("[greeting] normalised=%r hit=%s", norm, ctx.greeting)
    return ctx


def ner_stage(ctx: PipelineContext) -> PipelineContext:
    """Run the PhoBERT NER model and attach the recognised spans."""
    if not ctx.text:
        return ctx
    ctx.spans = list(extract_entities(ctx.text))
    log.info("[ner] extracted=%d spans=%s", len(ctx.spans),
             [{"surface": e.surface, "tag": e.tag,
               "start": e.start, "end": e.end} for e in ctx.spans])
    return ctx


def fuzzy_stage(ctx: PipelineContext) -> PipelineContext:
    """Resolve every span to its best ontology individual (above threshold)."""
    for ent in ctx.spans:
        candidates = search(ent.surface, ent.tag, top_k=3)
        log.info("[fuzzy] surface=%r tag=%s candidates=%s",
                 ent.surface, ent.tag,
                 [(c.iri, round(c.score, 2)) for c in candidates])
        m = best(ent.surface, ent.tag)
        if m is None:
            log.info("[fuzzy] reject surface=%r tag=%s (below threshold)",
                     ent.surface, ent.tag)
            continue
        ctx.matches.append((ent.tag, m))
        log.info("[fuzzy] pick surface=%r tag=%s -> iri=%s score=%.2f",
                 ent.surface, ent.tag, m.iri, m.score)
    return ctx


def render_stage(ctx: PipelineContext) -> PipelineContext:
    """Render every matched individual into a per-class reply block."""
    ctx.blocks = render_blocks(ctx.matches)
    return ctx


def compose_stage(ctx: PipelineContext) -> PipelineContext:
    """Glue greeting + ontology blocks (or fall back to OOD)."""
    ctx.reply = compose(ctx.blocks, greeting=ctx.greeting)
    log.info("[compose] greeting=%s n_matched=%d block_chars=%d reply_chars=%d",
             ctx.greeting, len(ctx.matches), len(ctx.blocks), len(ctx.reply))
    return ctx


# Pipeline runner

@dataclass(frozen=True)
class Pipeline:
    """Composes an ordered list of stages and runs them on a query string."""
    stages: Sequence[Stage]

    def run(self, query: str) -> dict:
        ctx = PipelineContext(query=query)
        if not (query or "").strip():
            log.info("[skip] empty input -> greeting reply")
            ctx.greeting = True
            ctx.reply = compose("", greeting=True)
            return ctx.to_response()
        for stage in self.stages:
            ctx = stage(ctx)
        return ctx.to_response()


DEFAULT_STAGES: tuple[Stage, ...] = (
    trim_stage,
    greeting_stage,
    ner_stage,
    fuzzy_stage,
    render_stage,
    compose_stage,
)

DEFAULT_PIPELINE = Pipeline(stages=DEFAULT_STAGES)


def answer(query: str) -> dict:
    """Process a single user query and return ``{reply, greeting, entities}``."""
    return DEFAULT_PIPELINE.run(query)
