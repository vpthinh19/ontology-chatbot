"""Pipeline: query → reply, wiring the three layers.

    understand (text→Query)  →  answer (Query→Fact[])  →  render (Fact[]→str)

One direction of dependency, no shared mutable state. :meth:`answer` is
synchronous (scripts, tests); :meth:`aanswer` offloads it to a worker thread
for FastAPI. The response shape ``{"reply", "entities"}`` is preserved so the
server and web UI need no change.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from . import answer as answer_mod
from . import nlu
from .answer import Fact
from .graph import Graph

log = logging.getLogger(__name__)


class Pipeline:
    """Understand → answer → render, over a single shared :class:`Graph`."""

    def __init__(self, graph: Graph | None = None) -> None:
        self.graph = graph or Graph.get()

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Pipeline":
        return cls()

    def answer(self, query: str) -> dict:
        """Synchronous entry — returns the ``/chat`` JSON dict."""
        q = nlu.understand(query)
        facts = answer_mod.answer(q, self.graph)
        reply = _render(q, facts)
        log.info("[pipeline] intent=%s facts=%d reply_chars=%d",
                 q.intent, len(facts), len(reply))
        return {"reply": reply, "entities": _entities(facts)}

    async def aanswer(self, query: str) -> dict:
        """Async entry — runs :meth:`answer` in a worker thread."""
        return await asyncio.to_thread(self.answer, query)


def _render(q, facts: list[Fact]) -> str:
    # Imported lazily so the answer/test layers can use the pipeline without
    # pulling the renderer's string templates.
    from .render import render_reply
    return render_reply(q, facts)


def _entities(facts: list[Fact]) -> list[dict]:
    """Flatten the resolved anchor(s) into the response's debug list.

    The anchor is the ``subject`` of a relation fact, or the ``objects`` of a
    self-set / listing fact. Deduped by IRI, declaration order preserved.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for f in facts:
        nodes = [f.subject] if f.subject is not None else f.objects
        for n in nodes:
            if n is None or n.iri in seen:
                continue
            seen.add(n.iri)
            out.append({"iri": n.iri, "label": n.label, "class": n.cls,
                        "intent": f.intent})
    return out
