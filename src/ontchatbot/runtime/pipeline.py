"""End-to-end question answering over the ontology."""

from __future__ import annotations

import logging
import time
import uuid

from rdflib import Graph

from .gate import DomainGate
from .model import QueryGenerator
from .render import render_rows
from .sparql import execute_select, load_ontology
from .text import normalize_model_input


logger = logging.getLogger(__name__)


OUT_OF_SCOPE_REPLY = (
    "Xin lỗi, tôi chỉ có thể trả lời các câu hỏi thuộc phạm vi học vụ hiện có."
)


class OutOfScopeError(ValueError):
    """Raised when the domain gate rejects a question."""


class OntologyChatbot:
    """Connect a query generator to the canonical RDF graph."""

    def __init__(
        self,
        generator: QueryGenerator,
        gate: DomainGate,
        graph: Graph | None = None,
    ) -> None:
        self.generator = generator
        self.gate = gate
        self.graph = graph if graph is not None else load_ontology()

    def answer(self, question: str) -> str:
        request_id = uuid.uuid4().hex[:12]
        request_started = time.perf_counter()
        normalized = normalize_model_input(question)
        logger.info(
            "request=%s input=%r normalized=%r",
            request_id,
            question,
            normalized,
        )
        stage = "gate"
        try:
            stage_started = time.perf_counter()
            decision = self.gate.decide(question)
            logger.info(
                "request=%s gate probability=%.6f threshold=%.6f "
                "accepted=%s duration_ms=%.1f",
                request_id,
                decision.probability,
                self.gate.threshold,
                str(decision.accepted).lower(),
                (time.perf_counter() - stage_started) * 1000,
            )
            if not decision.accepted:
                logger.info(
                    "request=%s rejected total_ms=%.1f",
                    request_id,
                    (time.perf_counter() - request_started) * 1000,
                )
                raise OutOfScopeError(OUT_OF_SCOPE_REPLY)

            stage = "generator"
            stage_started = time.perf_counter()
            query = self.generator.generate(question)
            logger.info(
                "request=%s generator sparql=%r duration_ms=%.1f",
                request_id,
                query,
                (time.perf_counter() - stage_started) * 1000,
            )

            stage = "ontology"
            stage_started = time.perf_counter()
            rows = execute_select(self.graph, query)
            logger.info(
                "request=%s ontology rows=%d duration_ms=%.1f",
                request_id,
                len(rows),
                (time.perf_counter() - stage_started) * 1000,
            )

            stage = "renderer"
            reply = render_rows(rows)
            logger.info(
                "request=%s reply=%r total_ms=%.1f",
                request_id,
                reply,
                (time.perf_counter() - request_started) * 1000,
            )
            return reply
        except OutOfScopeError:
            raise
        except Exception:
            logger.exception("request=%s stage=%s failed", request_id, stage)
            raise
