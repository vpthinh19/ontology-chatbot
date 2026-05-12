"""Answer pipeline: query → reply via 5 stages
(preprocess, ner, match, query, present).

Each stage is a method that mutates the shared :class:`PipelineContext`.
:meth:`Pipeline.answer` is synchronous; :meth:`Pipeline.aanswer` wraps it
via :func:`asyncio.to_thread` for FastAPI.

Greeting detection and out-of-domain fallback are owned by
:class:`Renderer.render_reply` — Pipeline carries no greeting state.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from functools import lru_cache

from .ner_model import Entity, NerModel
from .ontology import MatchResult, Ontology
from .preprocessor import Preprocessor
from .renderer import Renderer

log = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Mutable DTO threaded through the stages; fields accumulate top-down."""
    query: str
    text: str = ""
    words: list[str] = field(default_factory=list)
    spans: list[Entity] = field(default_factory=list)
    matches: list[MatchResult] = field(default_factory=list)
    descriptions: list[dict] = field(default_factory=list)
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
        return {"reply": self.reply, "entities": entities}


class Pipeline:
    """Orchestrate query → reply via 4 injected singleton collaborators."""

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
        """Synchronous entry — scripts, tests, and the async wrapper."""
        ctx = PipelineContext(query=query)
        return self._present(self._query(self._match(self._ner(
            self._preprocess(ctx))))).to_response()

    async def aanswer(self, query: str) -> dict:
        """Async entry — runs :meth:`answer` in a worker thread."""
        return await asyncio.to_thread(self.answer, query)

    # Stages — one collaborator each

    def _preprocess(self, ctx: PipelineContext) -> PipelineContext:
        """Strip raw query; clean + word-segment so NerModel gets pure tokens.

        Empty input short-circuits here: ``ctx.words`` stays empty and
        every downstream stage no-ops on the guard ``if not ctx.words``.
        Renderer treats an empty-text + empty-descriptions situation as a
        greeting trigger.
        """
        ctx.text = (ctx.query or "").strip()
        if not ctx.text:
            log.info("[Pipeline.preprocess] skip empty input")
            return ctx
        ctx.words = self.pre.clean_and_segment(ctx.text)
        log.info("[Pipeline.preprocess] text=%r words(n=%d)=%s",
                 ctx.text, len(ctx.words), ctx.words)
        return ctx

    def _ner(self, ctx: PipelineContext) -> PipelineContext:
        """Extract BIO spans from pre-segmented words."""
        if not ctx.words:
            return ctx
        ctx.spans = list(self.ner.extract_entities(ctx.words))
        log.info("[Pipeline.ner] extracted=%d spans=%s", len(ctx.spans),
                 [{"surface": e.surface, "tag": e.tag,
                   "start": e.start, "end": e.end} for e in ctx.spans])
        return ctx

    def _match(self, ctx: PipelineContext) -> PipelineContext:
        """Resolve each span to a :class:`MatchResult`."""
        for ent in ctx.spans:
            res = self.onto.resolve(ent.surface, ent.tag)
            if res.class_won or res.individuals:
                ctx.matches.append(res)
        log.info("[Pipeline.match] matched=%d", len(ctx.matches))
        return ctx

    def _query(self, ctx: PipelineContext) -> PipelineContext:
        """Serialise each match into a JSON description dict."""
        for m in ctx.matches:
            if m.class_won:
                ctx.descriptions.append(self.onto.list_class(m.tag))
                continue
            for iri in m.individuals:
                # depth=2: top-level entity carries full data, AND its
                # object-property targets carry their own data fields too
                # (e.g. each ``Phi_K65_*`` exposes feePerCredit + appliesToTarget).
                d = self.onto.describe(iri, depth=2)
                if d:
                    ctx.descriptions.append(d)
        log.info("[Pipeline.query] descriptions=%d", len(ctx.descriptions))
        return ctx

    def _present(self, ctx: PipelineContext) -> PipelineContext:
        """Hand text + descriptions to Renderer; greeting policy lives there."""
        ctx.reply = self.render.render_reply(ctx.text, ctx.descriptions)
        log.info("[Pipeline.present] descriptions=%d reply_chars=%d",
                 len(ctx.descriptions), len(ctx.reply))
        return ctx
