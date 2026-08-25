"""End-to-end question answering over the ontology."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence, TypeAlias

from rdflib import Graph

from ..catalogue import QuerySpec, find_query_family, load_catalogue
from ..settings import QUERY_CATALOGUE_PATH
from .generator import QueryGenerationError, QueryGenerator
from .render import NO_INFORMATION_REPLY, render_batch, render_rows
from .sparql import Primitive, QueryRows, SparqlError, execute_select, load_ontology
from .text import normalize_model_input


logger = logging.getLogger(__name__)

#: Chuỗi mà model sinh ra thay cho truy vấn khi câu hỏi nằm ngoài phần dữ liệu
#: đã biết. Nó là một đích được dạy, không phải lỗi.
MARKER = "không có thông tin"


@dataclass(frozen=True)
class PreparedKeyword:
    original: str
    model_input: str


@dataclass(frozen=True)
class Classification:
    label: str
    query: str | None


FrozenRow: TypeAlias = tuple[tuple[str, Primitive], ...]
FrozenRows: TypeAlias = tuple[FrozenRow, ...]


@dataclass(frozen=True)
class QueryResolution:
    status: Literal["ok", "query-failed"]
    rows: FrozenRows


def freeze_rows(rows: QueryRows) -> FrozenRows:
    """Freeze SPARQL output without changing its row or column order."""

    return tuple(tuple(row.items()) for row in rows)


def thaw_rows(rows: FrozenRows) -> QueryRows:
    """Restore frozen SPARQL output for the existing rendering boundary."""

    return [dict(row) for row in rows]


class OntologyChatbot:
    """Connect a query generator to the canonical RDF graph."""

    def __init__(
        self,
        generator: QueryGenerator,
        graph: Graph | None = None,
        catalogue: Mapping[str, QuerySpec] | None = None,
    ) -> None:
        self.generator = generator
        self.graph = graph if graph is not None else load_ontology()
        # A syntactically valid SELECT can still combine an entity and a property
        # that no declared query family allows, which executes and answers with
        # data the question never asked for. An empty mapping disables the check.
        self.catalogue = (
            load_catalogue(QUERY_CATALOGUE_PATH) if catalogue is None else catalogue
        )

    def prepare_keywords(self, questions: Sequence[str]) -> tuple[PreparedKeyword, ...]:
        """Trim and normalize unique keywords while retaining their display form."""

        original_keywords = dict.fromkeys(question.strip() for question in questions)
        prepared = tuple(
            PreparedKeyword(original, normalize_model_input(original))
            for original in original_keywords
            if original
        )
        if not prepared:
            raise SparqlError("no keyword to look up")
        return prepared

    def classify_many(self, model_inputs: Sequence[str]) -> tuple[Classification, ...]:
        """Generate one concrete query per normalized keyword, with safe fallback."""

        try:
            outputs = self.generator.generate_many(model_inputs)
        except QueryGenerationError:
            outputs = []
            for model_input in model_inputs:
                try:
                    outputs.append(self.generator.generate(model_input).strip())
                except QueryGenerationError:
                    outputs.append(MARKER)
        return tuple(self._classification_for(output) for output in outputs)

    def execute_query(self, query: str, *, max_rows: int = 100) -> QueryResolution:
        """Execute a concrete query, reserving failure status for SPARQL errors."""

        try:
            return QueryResolution(
                "ok", freeze_rows(execute_select(self.graph, query, max_rows=max_rows))
            )
        except SparqlError:
            return QueryResolution("query-failed", ())

    def render_many(
        self,
        prepared: Sequence[PreparedKeyword],
        choices: Sequence[Classification],
        resolutions: Mapping[str, QueryResolution],
    ) -> str:
        """Merge query outcomes into the established batched render contract."""

        rows: list[FrozenRow] = []
        seen: set[FrozenRow] = set()
        missed: list[str] = []
        for keyword, choice in zip(prepared, choices):
            if choice.query is None:
                missed.append(keyword.original)
                continue
            resolution = resolutions[choice.query]
            if resolution.status == "query-failed" or not resolution.rows:
                missed.append(keyword.original)
                continue
            for row in resolution.rows:
                if row not in seen:
                    seen.add(row)
                    rows.append(row)
        return render_batch(thaw_rows(tuple(rows)), missed=missed)

    def answer(self, question: str) -> str:
        request_id = uuid.uuid4().hex[:12]
        request_started = time.perf_counter()
        prepared = self.prepare_keywords([question])
        keyword = prepared[0]
        logger.debug(
            "request=%s input=%r normalized=%r",
            request_id,
            question,
            keyword.model_input,
        )
        stage = "generator"
        try:
            stage_started = time.perf_counter()
            output = self.generator.generate(keyword.model_input).strip()
            logger.debug("request=%s model output=%r", request_id, output)
            logger.info(
                "request=%s stage=generator duration_ms=%.1f",
                request_id,
                (time.perf_counter() - stage_started) * 1000,
            )
            choice = self._classification_for(output)
            if choice.query is None:
                if choice.label == "off-catalogue":
                    logger.info(
                        "request=%s off-catalogue query rejected classification=%s total_ms=%.1f",
                        request_id,
                        choice.label,
                        (time.perf_counter() - request_started) * 1000,
                    )
                    logger.debug("request=%s reply=%r", request_id, NO_INFORMATION_REPLY)
                    return NO_INFORMATION_REPLY
                logger.info(
                    "request=%s classification=%s total_ms=%.1f",
                    request_id,
                    choice.label,
                    (time.perf_counter() - request_started) * 1000,
                )
                logger.debug("request=%s reply=%r", request_id, NO_INFORMATION_REPLY)
                return NO_INFORMATION_REPLY

            stage = "ontology"
            stage_started = time.perf_counter()
            resolution = self.execute_query(choice.query)
            rows = thaw_rows(resolution.rows)
            logger.info(
                "request=%s classification=%s rows=%d duration_ms=%.1f",
                request_id,
                choice.label,
                len(rows),
                (time.perf_counter() - stage_started) * 1000,
            )

            stage = "renderer"
            reply = render_rows(rows)
            logger.info(
                "request=%s classification=%s total_ms=%.1f",
                request_id,
                choice.label,
                (time.perf_counter() - request_started) * 1000,
            )
            logger.debug("request=%s reply=%r", request_id, reply)
            return reply
        except Exception:
            logger.exception("request=%s stage=%s failed", request_id, stage)
            raise

    def answer_many(self, questions: Sequence[str]) -> str:
        """Tra nhiều cách gọi của cùng một chủ đề trong một lượt."""

        prepared = self.prepare_keywords(questions)
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        logger.info("request=%s keywords=%d", request_id, len(prepared))
        logger.debug(
            "request=%s keywords=%r", request_id, [item.original for item in prepared]
        )

        try:
            choices = self.classify_many([item.model_input for item in prepared])
            queries = dict.fromkeys(choice.query for choice in choices if choice.query)
            resolutions = {query: self.execute_query(query) for query in queries}
            for keyword, choice in zip(prepared, choices):
                resolution = resolutions.get(choice.query) if choice.query else None
                row_count = len(resolution.rows) if resolution else 0
                label = (
                    "query-failed"
                    if resolution and resolution.status == "query-failed"
                    else choice.label
                )
                logger.info(
                    "request=%s label=%s rows=%d",
                    request_id,
                    label,
                    row_count,
                )
            reply = self.render_many(prepared, choices, resolutions)
        except Exception:
            logger.exception("request=%s stage=batch failed", request_id)
            raise

        logger.info(
            "request=%s keywords=%d rows=%d missed=%d total_ms=%.1f",
            request_id,
            len(prepared),
            sum(len(resolution.rows) for resolution in resolutions.values()),
            sum(
                choice.query is None
                or resolutions[choice.query].status == "query-failed"
                or not resolutions[choice.query].rows
                for choice in choices
            ),
            (time.perf_counter() - started) * 1000,
        )
        logger.debug("request=%s reply=%r", request_id, reply)
        return reply

    def _classification_for(self, output: str) -> Classification:
        output = output.strip()
        if not output or output == MARKER:
            return Classification("no-information", None)
        query_id = find_query_family(self.catalogue, output) if self.catalogue else None
        if self.catalogue and query_id is None:
            return Classification("off-catalogue", None)
        return Classification(query_id or "unchecked", output)

    def _rows_for(self, output: str) -> tuple[str, QueryRows]:
        """Run output through the shared classification and execution rules."""

        choice = self._classification_for(output)
        if choice.query is None:
            return choice.label, []
        resolution = self.execute_query(choice.query)
        label = "query-failed" if resolution.status == "query-failed" else choice.label
        return label, thaw_rows(resolution.rows)
