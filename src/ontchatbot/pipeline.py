"""End-to-end answer pipeline as a 5-stage OOP composition.

Architecture
------------
:class:`Pipeline` injects four collaborator singletons —
:class:`Preprocessor`, :class:`NerModel`, :class:`Ontology`,
:class:`Renderer` — and runs them in a fixed sequence:

    preprocess → ner → match → query → present

Each step is one method on :class:`Pipeline`; the data-flow reads
top-to-bottom in :meth:`Pipeline.answer`. The :class:`PipelineContext` DTO
accumulates state along the chain so a partial run is still meaningful for
diagnostics if a stage decides to short-circuit.

Concurrency
~~~~~~~~~~~
Two entry points are exposed:

* :meth:`Pipeline.answer` — synchronous, suitable for scripts and tests.
* :meth:`Pipeline.aanswer` — async wrapper that runs :meth:`answer` via
  :func:`asyncio.to_thread`. PyTorch CUDA work is blocking C++, so the
  wrapper buys real concurrency on the FastAPI event loop without forcing
  every internal method to be ``async``.

Behavioural notes
~~~~~~~~~~~~~~~~~
* **Threshold-based fuzzy matching** — every individual scoring above the
  configured threshold is rendered, so ambiguous cohort spans (``"k65"``)
  surface *all* applicable fees instead of an arbitrary top-1.
* **Class-listing fallback** — when the matcher decides the user asked the
  class-level question, the renderer emits a flat list of every individual
  of that class instead of zooming into one.
* **Minimal-greeting policy** — substantive blocks always win; the bot only
  greets back when the user message is a pure greeting with no entity.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from functools import lru_cache

from ..ner.inference import Entity, NerModel
from ..ner.preprocessing import Preprocessor
from ..ontology.renderer import Renderer
from ..ontology.store import MatchResult, Ontology
from .config import GREETING_KEYWORDS

log = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """DTO threaded through the pipeline stages.

    Attributes accumulate top-down; partial contexts remain meaningful for
    diagnostics even if a stage short-circuits. Each stage adds one or two
    fields; nothing is removed mid-flight, which keeps trace logs complete.
    """
    query: str
    text: str = ""
    greeting: bool = False
    spans: list[Entity] = field(default_factory=list)
    matches: list[MatchResult] = field(default_factory=list)
    descriptions: list[dict] = field(default_factory=list)
    blocks: str = ""
    reply: str = ""

    def to_response(self) -> dict:
        """Serialise into the JSON shape returned by ``/chat``."""
        entities: list[dict] = []
        for ent, m in zip(self.spans, self.matches):
            entities.append({
                "surface": ent.surface,
                "tag": ent.tag,
                "class_won": m.class_won,
                "iris": list(m.individuals),
                "score": m.top_score,
            })
        return {
            "reply": self.reply,
            "greeting": self.greeting,
            "entities": entities,
        }


class Pipeline:
    """Orchestrate query → reply via injected singleton collaborators."""

    def __init__(self,
                 *,
                 preprocessor: Preprocessor | None = None,
                 ner: NerModel | None = None,
                 ontology: Ontology | None = None,
                 renderer: Renderer | None = None) -> None:
        self.pre = preprocessor or Preprocessor.get()
        self.ner = ner or NerModel.get()
        self.onto = ontology or Ontology.get()
        self.render = renderer or Renderer.get()

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Pipeline":
        return cls()

    # Public entry points

    def answer(self, query: str) -> dict:
        """Synchronous entry. Used by scripts, tests, and (via to_thread)
        by the async entry below."""
        ctx = PipelineContext(query=query)
        if not (query or "").strip():
            log.info("[Pipeline] skip empty input")
            ctx.greeting = True
            ctx.reply = self.render.compose("", greeting=True)
            return ctx.to_response()
        return self._present(self._query(self._match(self._ner(
            self._preprocess(ctx))))).to_response()

    async def aanswer(self, query: str) -> dict:
        """Async wrapper for FastAPI. Runs :meth:`answer` in a worker
        thread so the event loop stays free during PyTorch inference."""
        return await asyncio.to_thread(self.answer, query)

    # Stages — one collaborator each

    def _preprocess(self, ctx: PipelineContext) -> PipelineContext:
        """Trim whitespace and detect a greeting in one pass.

        Both behaviours are pure text manipulation upstream of the model;
        keeping them together documents the invariant that nothing past
        this stage touches raw user characters.
        """
        ctx.text = (ctx.query or "").strip()
        if ctx.text:
            norm = self.pre.strip_diacritics(ctx.text.lower()).strip()
            ctx.greeting = any(kw in norm for kw in GREETING_KEYWORDS)
        log.info("[Pipeline.preprocess] text=%r greeting=%s",
                 ctx.text, ctx.greeting)
        return ctx

    def _ner(self, ctx: PipelineContext) -> PipelineContext:
        """Extract BIO spans via the injected :class:`NerModel`."""
        if not ctx.text:
            return ctx
        ctx.spans = list(self.ner.extract_entities(ctx.text))
        log.info("[Pipeline.ner] extracted=%d spans=%s", len(ctx.spans),
                 [{"surface": e.surface, "tag": e.tag,
                   "start": e.start, "end": e.end} for e in ctx.spans])
        return ctx

    def _match(self, ctx: PipelineContext) -> PipelineContext:
        """Resolve every span to a :class:`MatchResult` (class or individuals)."""
        for ent in ctx.spans:
            res = self.onto.resolve(ent.surface, ent.tag)
            if res.class_won or res.individuals:
                ctx.matches.append(res)
        log.info("[Pipeline.match] matched=%d", len(ctx.matches))
        return ctx

    def _query(self, ctx: PipelineContext) -> PipelineContext:
        """Convert each :class:`MatchResult` into JSON descriptions.

        The Ontology is the only layer that knows how to serialise into the
        property-label-keyed contract; from this point on we operate on
        plain dicts.
        """
        for m in ctx.matches:
            if m.class_won:
                ctx.descriptions.append(self.onto.list_class(m.tag))
                continue
            for iri in m.individuals:
                d = self.onto.describe(iri, depth=1)
                if d:
                    ctx.descriptions.append(d)
        log.info("[Pipeline.query] descriptions=%d", len(ctx.descriptions))
        return ctx

    def _present(self, ctx: PipelineContext) -> PipelineContext:
        """Render JSON descriptions to text and apply the greeting policy.

        Folds the previous ``_render`` and ``_compose`` stages because both
        are short pure-presentation steps; one log line is enough to trace.
        """
        ctx.blocks = self.render.render_blocks(ctx.descriptions)
        ctx.reply = self.render.compose(ctx.blocks, greeting=ctx.greeting)
        log.info("[Pipeline.present] blocks=%d greeting=%s reply_chars=%d",
                 len(ctx.descriptions), ctx.greeting, len(ctx.reply))
        return ctx
