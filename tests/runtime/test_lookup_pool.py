from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
import json
import logging
import re
import threading
import time

import httpx
import pytest

from ontchatbot.runtime.agent import look_up_async
from ontchatbot.runtime.api import create_app
from ontchatbot.runtime.lookup_pool import AsyncLookupPool, _NativeWorkers
from ontchatbot.runtime.pipeline import (
    Classification,
    PreparedKeyword,
    QueryResolution,
)
from ontchatbot.runtime.render import NO_INFORMATION_REPLY
from ontchatbot.runtime.sparql import SparqlError


_ROW = ((('answer', 'dữ kiện'),),)


class _FakeChatbot:
    query = 'SELECT ?answer WHERE { :Example :value ?answer . }'

    def __init__(self) -> None:
        self.classification_batches: list[tuple[str, ...]] = []
        self.executed_queries: list[str] = []
        self.executed_limits: list[int] = []
        self.queries_by_input: dict[str, str | None] = {}
        self.resolutions: dict[str, QueryResolution] = {}

    def prepare_keywords(self, questions) -> tuple[PreparedKeyword, ...]:
        return tuple(PreparedKeyword(value, value) for value in dict.fromkeys(questions))

    def classify_many(self, model_inputs) -> tuple[Classification, ...]:
        keys = tuple(model_inputs)
        self.classification_batches.append(keys)
        return tuple(
            Classification('same-family', self.queries_by_input.get(key, self.query))
            for key in keys
        )

    def execute_query(self, query: str, *, max_rows: int) -> QueryResolution:
        self.executed_queries.append(query)
        self.executed_limits.append(max_rows)
        return self.resolutions.get(query, QueryResolution('ok', _ROW))

    def render_many(self, prepared, choices, resolutions) -> str:
        return json.dumps(
            {
                'keywords': [item.original for item in prepared],
                'labels': [choice.label for choice in choices],
                'statuses': {
                    query: resolution.status
                    for query, resolution in resolutions.items()
                },
                'rows': {
                    query: resolution.rows for query, resolution in resolutions.items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )


class _BlockingClassifier(_FakeChatbot):
    def __init__(self, blocked: str = 'đăng ký học phần') -> None:
        super().__init__()
        self.blocked = blocked
        self.started = threading.Event()
        self.release = threading.Event()
        self.other_started = threading.Event()

    def classify_many(self, model_inputs) -> tuple[Classification, ...]:
        keys = tuple(model_inputs)
        if self.blocked in keys:
            self.started.set()
            self.release.wait(timeout=2)
        else:
            self.other_started.set()
        return super().classify_many(keys)


async def _wait_until(predicate, *, timeout: float = 1) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0)


def test_fifty_identical_cold_lookups_compute_each_stage_once() -> None:
    fake = _FakeChatbot()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=4)
        try:
            results = await asyncio.gather(*(
                pool(['đăng ký học phần']) for _ in range(50)
            ))
            assert len(set(results)) == 1
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.classification_batches == [('đăng ký học phần',)]
    assert fake.executed_queries == [fake.query]
    assert fake.executed_limits == [100]


def test_tool_info_log_reports_only_bounded_cache_and_render_metrics(caplog) -> None:
    fake = _FakeChatbot()

    async def exercise() -> str:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            return await pool(["question only for the fake"])
        finally:
            await pool.aclose()

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.lookup_pool"):
        rendered = asyncio.run(exercise())

    trace = "\n".join(record.getMessage() for record in caplog.records)
    for field in (
        "lookup=",
        "keywords=1",
        "l1_hits=",
        "l1_misses=",
        "l1_followers=",
        "l1_evictions=",
        "l3_hits=",
        "l3_misses=",
        "l3_followers=",
        "l3_evictions=",
        "native_peak=",
        "rows=",
        "rendered_bytes=",
        "duration_ms=",
    ):
        assert field in trace
    assert "question only for the fake" not in trace
    assert fake.query not in trace
    assert "dữ kiện" not in trace
    metrics = dict(field.split("=", 1) for field in trace.split())
    assert metrics["status"] == "ok"
    assert metrics["l1_hits"] == "0"
    assert metrics["l1_misses"] == "1"
    assert metrics["l1_followers"] == "0"
    assert metrics["l1_evictions"] == "0"
    assert metrics["l3_hits"] == "0"
    assert metrics["l3_misses"] == "1"
    assert metrics["l3_followers"] == "0"
    assert metrics["l3_evictions"] == "0"
    assert metrics["native_peak"] == "1"
    assert metrics["rows"] == "1"
    assert metrics["rendered_bytes"] == str(len(rendered.encode("utf-8")))


def test_concurrent_lookup_logs_attribute_each_cache_outcome_once(caplog) -> None:
    fake = _BlockingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=2)
        tasks = [asyncio.create_task(pool(["đăng ký học phần"])) for _ in range(50)]
        try:
            await _wait_until(fake.started.is_set)
            await _wait_until(lambda: pool.stats.classifications.followers == 49)
            fake.release.set()
            await asyncio.gather(*tasks)
        finally:
            fake.release.set()
            await pool.aclose()

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.lookup_pool"):
        asyncio.run(exercise())

    records = [
        record.getMessage()
        for record in caplog.records
        if record.name == "ontchatbot.runtime.lookup_pool"
    ]
    assert len(records) == 50
    for metric, expected in (
        ("l1_hits", 0),
        ("l1_misses", 1),
        ("l1_followers", 49),
        ("l3_hits", 0),
        ("l3_misses", 1),
        ("l3_followers", 49),
    ):
        assert sum(
            int(re.search(fr"{metric}=(\d+)", record).group(1))
            for record in records
        ) == expected


def test_expected_lookup_error_still_emits_one_bounded_terminal_log(caplog) -> None:
    class RejectedKeywords(_FakeChatbot):
        def prepare_keywords(self, _questions):
            raise SparqlError("sensitive validation detail")

    async def exercise() -> None:
        pool = AsyncLookupPool(RejectedKeywords(), workers=1)
        try:
            return await look_up_async(pool, ["học phí"])
        finally:
            await pool.aclose()

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.lookup_pool"):
        reply = asyncio.run(exercise())

    records = [
        record.getMessage()
        for record in caplog.records
        if record.name == "ontchatbot.runtime.lookup_pool"
    ]
    assert reply == NO_INFORMATION_REPLY
    assert len(records) == 1
    assert "status=expected-error" in records[0]
    assert "duration_ms=" in records[0]
    assert "lookup=" in records[0]
    assert "sensitive validation detail" not in records[0]


def test_cancelled_lookup_log_is_stable_while_the_shared_query_evicts(caplog) -> None:
    class BlockingQuery(_FakeChatbot):
        def __init__(self) -> None:
            super().__init__()
            self.queries_by_input = {"old": "old", "new": "new"}
            self.started = threading.Event()
            self.release = threading.Event()

        def execute_query(self, query: str, *, max_rows: int) -> QueryResolution:
            if query == "new":
                self.started.set()
                self.release.wait(timeout=2)
            return super().execute_query(query, max_rows=max_rows)

    fake = BlockingQuery()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1, sparql_cache_bytes=40)
        try:
            await pool(["old"])
            leader = asyncio.create_task(pool(["new"]))
            await _wait_until(fake.started.is_set)
            follower = asyncio.create_task(pool(["new"]))
            await _wait_until(lambda: pool.stats.queries.followers == 1)
            leader.cancel()
            with pytest.raises(asyncio.CancelledError):
                await leader
            fake.release.set()
            assert await follower
            assert pool.stats.queries.evictions == 1
        finally:
            fake.release.set()
            await pool.aclose()

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.lookup_pool"):
        asyncio.run(exercise())

    cancelled = next(
        record.getMessage()
        for record in caplog.records
        if "status=cancelled" in record.getMessage()
    )
    assert "l3_misses=1" in cancelled
    assert "l3_evictions=0" in cancelled


def test_closed_pool_rejection_emits_one_bounded_terminal_log(caplog) -> None:
    async def exercise() -> None:
        pool = AsyncLookupPool(_FakeChatbot(), workers=1)
        await pool.aclose()
        with pytest.raises(RuntimeError, match="closed"):
            await pool(["học phí"])

    with caplog.at_level(logging.INFO, logger="ontchatbot.runtime.lookup_pool"):
        asyncio.run(exercise())

    records = [
        record.getMessage()
        for record in caplog.records
        if record.name == "ontchatbot.runtime.lookup_pool"
    ]
    assert len(records) == 1
    assert "status=closed" in records[0]
    assert "học phí" not in records[0]


def test_pool_never_runs_more_than_four_native_jobs_at_once() -> None:
    class PeakFake(_FakeChatbot):
        def __init__(self) -> None:
            super().__init__()
            self.live = 0
            self.peak = 0
            self.lock = threading.Lock()
            self.four_entered = threading.Event()

        def classify_many(self, model_inputs) -> tuple[Classification, ...]:
            with self.lock:
                self.live += 1
                self.peak = max(self.peak, self.live)
                if self.live == 4:
                    self.four_entered.set()
            try:
                self.four_entered.wait(timeout=2)
                time.sleep(0.01)
                return super().classify_many(model_inputs)
            finally:
                with self.lock:
                    self.live -= 1

    fake = PeakFake()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=4)
        try:
            await asyncio.gather(*(pool([f'từ khoá {index}']) for index in range(12)))
            assert pool.stats.native.peak == 4
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.peak == 4


def test_a_blocked_native_job_does_not_block_healthz() -> None:
    fake = _BlockingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        task = asyncio.create_task(pool(['đăng ký học phần']))
        try:
            await _wait_until(fake.started.is_set)
            transport = httpx.ASGITransport(app=create_app(object()))
            async with httpx.AsyncClient(
                transport=transport, base_url='http://test'
            ) as client:
                response = await asyncio.wait_for(client.get('/healthz'), timeout=0.05)
            assert response.json() == {'status': 'ok'}
        finally:
            fake.release.set()
            await task
            await pool.aclose()

    asyncio.run(exercise())


def test_l1_hit_skips_the_classifier() -> None:
    fake = _FakeChatbot()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            first = await pool(['học phí'])
            second = await pool(['học phí'])
            assert first == second
            assert pool.stats.classifications.hits == 1
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.classification_batches == [('học phí',)]


@pytest.mark.parametrize('label', ['no-information', 'off-catalogue'])
def test_deterministic_no_query_classifications_are_cached(label) -> None:
    class NoQueryFake(_FakeChatbot):
        def classify_many(self, model_inputs) -> tuple[Classification, ...]:
            keys = tuple(model_inputs)
            self.classification_batches.append(keys)
            return tuple(Classification(label, None) for _key in keys)

    fake = NoQueryFake()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            await pool(['ngoài dữ liệu'])
            await pool(['ngoài dữ liệu'])
            assert pool.stats.classifications.hits == 1
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.classification_batches == [('ngoài dữ liệu',)]
    assert fake.executed_queries == []


def test_l3_hit_skips_sparql_for_a_distinct_classification_key() -> None:
    fake = _FakeChatbot()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            await pool(['cách đóng học phí'])
            await pool(['thanh toán học phí'])
            assert pool.stats.queries.hits == 1
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.executed_queries == [fake.query]


def test_two_concrete_queries_in_one_family_have_distinct_l3_entries() -> None:
    fake = _FakeChatbot()
    first = 'SELECT ?answer WHERE { :First :value ?answer . }'
    second = 'SELECT ?answer WHERE { :Second :value ?answer . }'
    fake.queries_by_input = {'một': first, 'hai': second}

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            await pool(['một', 'hai'])
            await pool(['một', 'hai'])
            assert pool.stats.queries.hits == 2
            assert pool.stats.native.submitted == 2
            assert pool.stats.native.peak == 1
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.executed_queries == [first, second]


def test_successful_empty_rows_are_cached() -> None:
    fake = _FakeChatbot()
    fake.resolutions[fake.query] = QueryResolution('ok', ())

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            assert await pool(['không có hàng']) == await pool(['không có hàng'])
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.executed_queries == [fake.query]


def test_query_failure_is_returned_but_retried() -> None:
    class FailingQuery(_FakeChatbot):
        def execute_query(self, query: str, *, max_rows: int) -> QueryResolution:
            super().execute_query(query, max_rows=max_rows)
            return QueryResolution(
                'query-failed' if len(self.executed_queries) == 1 else 'ok',
                () if len(self.executed_queries) == 1 else _ROW,
            )

    fake = FailingQuery()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            first = json.loads(await pool(['học phí']))
            second = json.loads(await pool(['học phí']))
            assert first['statuses'][fake.query] == 'query-failed'
            assert second['statuses'][fake.query] == 'ok'
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.executed_queries == [fake.query, fake.query]


def test_query_exception_cleans_inflight_without_caching_a_partial_batch() -> None:
    class ExceptionalQuery(_FakeChatbot):
        def __init__(self) -> None:
            super().__init__()
            self.fail = True

        def execute_query(self, query: str, *, max_rows: int) -> QueryResolution:
            value = super().execute_query(query, max_rows=max_rows)
            if self.fail and query == second:
                raise RuntimeError("graph unavailable")
            return value

    first = "SELECT ?answer WHERE { :First :value ?answer . }"
    second = "SELECT ?answer WHERE { :Second :value ?answer . }"
    fake = ExceptionalQuery()
    fake.queries_by_input = {"một": first, "hai": second}

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        try:
            with pytest.raises(RuntimeError, match="graph unavailable"):
                await pool(["một", "hai"])
            assert pool.stats.native.failed == 1
            assert pool.stats.queries.current_weight == 0
            fake.fail = False
            assert await pool(["một", "hai"])
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.executed_queries == [first, second, first, second]


def test_forty_nine_followers_consume_no_native_slots() -> None:
    fake = _BlockingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=2)
        tasks = [
            asyncio.create_task(pool(['đăng ký học phần'])) for _ in range(50)
        ]
        try:
            await _wait_until(fake.started.is_set)
            await _wait_until(lambda: pool.stats.classifications.followers == 49)
            assert pool.stats.native.submitted == 1
            assert pool.stats.native.active == 1
        finally:
            fake.release.set()
            await asyncio.gather(*tasks)
            await pool.aclose()

    asyncio.run(exercise())


def test_an_unrelated_miss_runs_while_followers_wait() -> None:
    fake = _BlockingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=2)
        followers = [
            asyncio.create_task(pool(['đăng ký học phần'])) for _ in range(50)
        ]
        unrelated = None
        try:
            await _wait_until(fake.started.is_set)
            await _wait_until(lambda: pool.stats.classifications.followers == 49)
            unrelated = asyncio.create_task(pool(['học bổng']))
            await _wait_until(fake.other_started.is_set)
            assert pool.stats.native.active == 2
        finally:
            fake.release.set()
            await asyncio.gather(*followers)
            if unrelated is not None:
                await unrelated
            await pool.aclose()

    asyncio.run(exercise())


def test_cancelling_during_classification_holds_the_worker_slot() -> None:
    fake = _BlockingClassifier(blocked='một')

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        first = asyncio.create_task(pool(['một']))
        try:
            await _wait_until(fake.started.is_set)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(pool(['hai']))
            await asyncio.sleep(0.02)
            assert not fake.other_started.is_set()
            assert pool.stats.native.active == 1
            fake.release.set()
            assert await asyncio.wait_for(second, timeout=0.5)
        finally:
            fake.release.set()
            await pool.aclose()

    asyncio.run(exercise())


def test_cancelling_during_sparql_holds_the_worker_slot() -> None:
    class BlockingQuery(_FakeChatbot):
        def __init__(self) -> None:
            super().__init__()
            self.query_started = threading.Event()
            self.query_release = threading.Event()
            self.second_classification_started = threading.Event()

        def classify_many(self, model_inputs) -> tuple[Classification, ...]:
            if 'hai' in model_inputs:
                self.second_classification_started.set()
            return super().classify_many(model_inputs)

        def execute_query(self, query: str, *, max_rows: int) -> QueryResolution:
            self.query_started.set()
            self.query_release.wait(timeout=2)
            return super().execute_query(query, max_rows=max_rows)

    fake = BlockingQuery()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        first = asyncio.create_task(pool(['một']))
        try:
            await _wait_until(fake.query_started.is_set)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(pool(['hai']))
            await asyncio.sleep(0.02)
            assert not fake.second_classification_started.is_set()
            assert pool.stats.native.active == 1
            fake.query_release.set()
            assert await asyncio.wait_for(second, timeout=0.5)
        finally:
            fake.query_release.set()
            await pool.aclose()

    asyncio.run(exercise())


def test_repeated_cancellation_waits_for_native_work_before_releasing_slot() -> None:
    first_started = threading.Event()
    first_release = threading.Event()
    second_started = threading.Event()

    def first_job() -> str:
        first_started.set()
        first_release.wait(timeout=2)
        return 'một'

    def second_job() -> str:
        second_started.set()
        return 'hai'

    async def exercise() -> None:
        workers = _NativeWorkers(1)
        first = asyncio.create_task(workers.run(first_job))
        try:
            await _wait_until(first_started.is_set)
            first.cancel()
            await asyncio.sleep(0)
            first.cancel()
            second = asyncio.create_task(workers.run(second_job))
            await asyncio.sleep(0.02)
            assert not second_started.is_set()
            assert workers.stats.active == 1
            first_release.set()
            with pytest.raises(asyncio.CancelledError):
                await first
            assert await asyncio.wait_for(second, timeout=0.5) == 'hai'
        finally:
            first_release.set()
            workers.close()

    asyncio.run(exercise())


def test_concurrent_failed_followers_share_the_error_and_later_retry() -> None:
    class FailingClassifier(_FakeChatbot):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()
            self.calls = 0

        def classify_many(self, model_inputs) -> tuple[Classification, ...]:
            self.calls += 1
            if self.calls == 1:
                self.started.set()
                self.release.wait(timeout=2)
                raise RuntimeError('model unavailable')
            return super().classify_many(model_inputs)

    fake = FailingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=2)
        tasks = [asyncio.create_task(pool(['same'])) for _ in range(50)]
        try:
            await _wait_until(fake.started.is_set)
            await _wait_until(lambda: pool.stats.classifications.followers == 49)
            fake.release.set()
            errors = await asyncio.gather(*tasks, return_exceptions=True)
            assert all(isinstance(error, RuntimeError) for error in errors)
            assert all(error is errors[0] for error in errors)
            assert await pool(['same'])
        finally:
            fake.release.set()
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.calls == 2


def test_zero_cache_budgets_keep_singleflight_without_retaining_values() -> None:
    fake = _BlockingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(
            fake,
            workers=2,
            classification_cache_entries=0,
            sparql_cache_bytes=0,
        )
        tasks = [asyncio.create_task(pool(['đăng ký học phần'])) for _ in range(2)]
        try:
            await _wait_until(fake.started.is_set)
            await _wait_until(lambda: pool.stats.classifications.followers == 1)
            fake.release.set()
            await asyncio.gather(*tasks)
            await pool(['đăng ký học phần'])
            assert pool.stats.classifications.current_weight == 0
            assert pool.stats.queries.current_weight == 0
        finally:
            fake.release.set()
            await pool.aclose()

    asyncio.run(exercise())
    assert len(fake.classification_batches) == 2
    assert fake.executed_queries == [fake.query, fake.query]


def test_oversized_query_result_is_returned_but_not_stored() -> None:
    fake = _FakeChatbot()
    fake.resolutions[fake.query] = QueryResolution(
        'ok', ((('answer', 'quá dài'),),)
    )

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1, sparql_cache_bytes=1)
        try:
            first = await pool(['học phí'])
            second = await pool(['học phí'])
            assert first == second
            assert pool.stats.queries.current_weight == 0
        finally:
            await pool.aclose()

    asyncio.run(exercise())
    assert fake.executed_queries == [fake.query, fake.query]


def test_stats_are_immutable_snapshots() -> None:
    fake = _FakeChatbot()

    async def exercise():
        pool = AsyncLookupPool(fake, workers=1)
        try:
            await pool(['học phí'])
            return pool.stats
        finally:
            await pool.aclose()

    stats = asyncio.run(exercise())
    assert stats.native.submitted == 2
    assert stats.native.completed == 2
    assert stats.native.failed == 0
    assert stats.classifications.misses == 1
    assert stats.queries.misses == 1
    with pytest.raises(FrozenInstanceError):
        stats.native.submitted = 3


def test_aclose_waits_for_loaders_and_leaves_no_executor_thread() -> None:
    fake = _BlockingClassifier()

    async def exercise() -> None:
        pool = AsyncLookupPool(fake, workers=1)
        request = asyncio.create_task(pool(['đăng ký học phần']))
        await _wait_until(fake.started.is_set)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        closing = asyncio.create_task(pool.aclose())
        await asyncio.sleep(0.02)
        assert not closing.done()
        fake.release.set()
        await closing

    asyncio.run(exercise())
    assert not any(
        thread.is_alive() and thread.name.startswith('ontology-lookup')
        for thread in threading.enumerate()
    )


@pytest.mark.parametrize('workers', [0, -1])
def test_pool_rejects_non_positive_worker_counts(workers) -> None:
    with pytest.raises(ValueError, match='workers must be positive'):
        AsyncLookupPool(_FakeChatbot(), workers=workers)
