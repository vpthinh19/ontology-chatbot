"""End-to-end question answering over the ontology."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Mapping, Sequence

from rdflib import Graph

from ..catalogue import QuerySpec, find_query_family, load_catalogue
from ..settings import QUERY_CATALOGUE_PATH
from .generator import QueryGenerationError, QueryGenerator
from .render import NO_INFORMATION_REPLY, render_batch, render_rows
from .sparql import QueryRows, execute_select, load_ontology
from .text import normalize_model_input


logger = logging.getLogger(__name__)

#: Chuỗi mà model sinh ra thay cho truy vấn khi câu hỏi nằm ngoài phần dữ liệu
#: đã biết. Nó là một đích được dạy, không phải lỗi.
MARKER = "không có thông tin"


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
            if output == MARKER:
                logger.info(
                    "request=%s reply=%r total_ms=%.1f",
                    request_id,
                    NO_INFORMATION_REPLY,
                    (time.perf_counter() - request_started) * 1000,
                )
                return NO_INFORMATION_REPLY

            stage = "catalogue"
            query_id = (
                find_query_family(self.catalogue, output) if self.catalogue else None
            )
            if self.catalogue and query_id is None:
                logger.info(
                    "request=%s off-catalogue query rejected reply=%r total_ms=%.1f",
                    request_id,
                    NO_INFORMATION_REPLY,
                    (time.perf_counter() - request_started) * 1000,
                )
                return NO_INFORMATION_REPLY

            stage = "ontology"
            stage_started = time.perf_counter()
            rows = execute_select(self.graph, output)
            logger.info(
                "request=%s ontology rows=%d duration_ms=%.1f query_id=%s",
                request_id,
                len(rows),
                (time.perf_counter() - stage_started) * 1000,
                query_id,
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

    def answer_many(self, questions: Sequence[str]) -> str:
        """Tra nhiều cách gọi của cùng một chủ đề trong một lượt.

        Người hỏi và ontology thường gọi một thứ bằng hai tên khác nhau, nên một
        cụm từ khoá có thể trượt trong khi cụm khác trúng. Gửi vài cụm cùng lúc
        làm tăng khả năng trúng mà vẫn chỉ tốn một lượt gọi.

        Suy luận chạy theo lô thật: cả loạt câu đi qua model một lần. Kết quả
        gộp lại và khử trùng, vì nhiều cụm cùng trúng một mục là chuyện thường -
        để nguyên thì cùng một dữ kiện xuất hiện vài lần.
        """

        wanted = [q for q in dict.fromkeys(q.strip() for q in questions) if q]
        if not wanted:
            raise SparqlError("no keyword to look up")
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        logger.info("request=%s batch=%r", request_id, wanted)

        try:
            outputs = self.generator.generate_many(wanted)
        except QueryGenerationError:
            outputs = []
            for question in wanted:
                try:
                    outputs.append(self.generator.generate(question).strip())
                except QueryGenerationError:
                    outputs.append(MARKER)

        rows: QueryRows = []
        seen: set[tuple] = set()
        missed = []
        for question, output in zip(wanted, outputs):
            found = self._rows_for(output.strip())
            if not found:
                missed.append(question)
                continue
            for row in found:
                key = tuple(sorted(row.items(), key=lambda item: item[0]))
                if key not in seen:
                    seen.add(key)
                    rows.append(row)

        logger.info(
            "request=%s batch rows=%d missed=%d total_ms=%.1f",
            request_id,
            len(rows),
            len(missed),
            (time.perf_counter() - started) * 1000,
        )
        return render_batch(rows, missed=missed)

    def _rows_for(self, output: str) -> QueryRows:
        """Chạy một truy vấn model sinh ra; mọi kiểu trượt đều trả về rỗng."""

        if not output or output == MARKER:
            return []
        if self.catalogue and find_query_family(self.catalogue, output) is None:
            return []
        try:
            return execute_select(self.graph, output)
        except SparqlError:
            return []
