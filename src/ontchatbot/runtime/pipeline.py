"""End-to-end question answering over the ontology."""

from __future__ import annotations

import logging
import time
import uuid

from rdflib import Graph

from .model import QueryGenerator
from .render import NO_INFORMATION_REPLY, render_rows
from .sparql import execute_select, load_ontology
from .text import normalize_model_input


logger = logging.getLogger(__name__)


class OntologyChatbot:
    """Connect a query generator to the canonical RDF graph."""

    def __init__(
        self,
        generator: QueryGenerator,
        graph: Graph | None = None,
    ) -> None:
        self.generator = generator
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
        stage = "generator"
        try:
            stage_started = time.perf_counter()
            output = self.generator.generate(question).strip()
            logger.info(
                "request=%s model output=%r duration_ms=%.1f",
                request_id,
                output,
                (time.perf_counter() - stage_started) * 1000,
            )
            if output == "không có thông tin":
                logger.info(
                    "request=%s reply=%r total_ms=%.1f",
                    request_id,
                    NO_INFORMATION_REPLY,
                    (time.perf_counter() - request_started) * 1000,
                )
                return NO_INFORMATION_REPLY

            stage = "ontology"
            stage_started = time.perf_counter()
            rows = execute_select(self.graph, output)
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
        except Exception:
            logger.exception("request=%s stage=%s failed", request_id, stage)
            raise
