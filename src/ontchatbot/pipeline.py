"""Answer pipeline: query → reply via 5 stages
(preprocess, ner, match, query, present).

Each stage is a method that mutates the shared :class:`PipelineContext`.
:meth:`Pipeline.answer` is synchronous; :meth:`Pipeline.aanswer` wraps it
via :func:`asyncio.to_thread` for FastAPI.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from functools import lru_cache

from .ner_model import Entity, NerModel
from .ontology import MatchResult, Ontology
from .preprocessor import Preprocessor
from .renderer import GREETING_KEYWORDS, Renderer

log = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Mutable DTO threaded through the stages; fields accumulate top-down."""
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
        if not (query or "").strip():
            log.info("[Pipeline] skip empty input")
            ctx.greeting = True
            ctx.reply = self.render.compose("", greeting=True)
            return ctx.to_response()
        return self._present(self._query(self._match(self._ner(
            self._preprocess(ctx))))).to_response()

    async def aanswer(self, query: str) -> dict:
        """Async entry — runs :meth:`answer` in a worker thread."""
        return await asyncio.to_thread(self.answer, query)

    # Stages — one collaborator each

    def _preprocess(self, ctx: PipelineContext) -> PipelineContext:
        """Trim whitespace and detect a greeting."""
        ctx.text = (ctx.query or "").strip()
        if ctx.text:
            norm = self.pre.strip_diacritics(ctx.text.lower()).strip()
            ctx.greeting = any(kw in norm for kw in GREETING_KEYWORDS)
        log.info("[Pipeline.preprocess] text=%r greeting=%s",
                 ctx.text, ctx.greeting)
        return ctx

    def _ner(self, ctx: PipelineContext) -> PipelineContext:
        """Extract BIO spans."""
        if not ctx.text:
            return ctx
        ctx.spans = list(self.ner.extract_entities(ctx.text))
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
        """Render to text + apply the greeting policy."""
        ctx.blocks = self.render.render_blocks(ctx.descriptions)
        ctx.reply = self.render.compose(ctx.blocks, greeting=ctx.greeting)
        log.info("[Pipeline.present] blocks=%d greeting=%s reply_chars=%d",
                 len(ctx.descriptions), ctx.greeting, len(ctx.reply))
        return ctx
