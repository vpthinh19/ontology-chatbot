"""Coordinate cached ontology lookups across bounded native workers."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from typing import ParamSpec, TypeVar

from .cache import BatchSingleFlightCache, CacheOutcome, CacheStats, Loaded
from .generator import QueryGenerationError
from .pipeline import Classification, OntologyChatbot, QueryResolution
from .sparql import SparqlError


P = ParamSpec("P")
T = TypeVar("T")
QueryKey = tuple[str, int]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NativeStats:
    submitted: int
    active: int
    peak: int
    completed: int
    failed: int
    worker_wait_ms: float


@dataclass(frozen=True)
class LookupStats:
    native: NativeStats
    classifications: CacheStats
    queries: CacheStats


async def _await_native_even_if_cancelled(future: asyncio.Future[T]) -> T:
    """Keep awaiting uninterruptible native work before propagating cancellation."""

    cancelled = False
    while True:
        try:
            result = await asyncio.shield(future)
        except asyncio.CancelledError:
            cancelled = True
            continue
        except BaseException:
            if cancelled:
                raise asyncio.CancelledError from None
            raise
        if cancelled:
            raise asyncio.CancelledError
        return result


class _NativeWorkers:
    def __init__(self, workers: int):
        if workers < 1:
            raise ValueError("workers must be positive")
        self._slots = asyncio.Semaphore(workers)
        self._executor = ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="ontology-lookup"
        )
        self._submitted = 0
        self._active = 0
        self._peak = 0
        self._completed = 0
        self._failed = 0
        self._worker_wait_ms = 0.0
        self._closed = False

    @property
    def stats(self) -> NativeStats:
        return NativeStats(
            submitted=self._submitted,
            active=self._active,
            peak=self._peak,
            completed=self._completed,
            failed=self._failed,
            worker_wait_ms=self._worker_wait_ms,
        )

    @property
    def closed(self) -> bool:
        return self._closed

    async def run(self, function: Callable[P, T], /, *args: P.args) -> T:
        wait_started = time.perf_counter()
        async with self._slots:
            self._worker_wait_ms += (time.perf_counter() - wait_started) * 1000
            if self._closed:
                raise RuntimeError("native workers are closed")
            self._submitted += 1
            self._active += 1
            self._peak = max(self._peak, self._active)
            loop = asyncio.get_running_loop()
            try:
                native = loop.run_in_executor(
                    self._executor, partial(function, *args)
                )
            except BaseException:
                self._active -= 1
                self._failed += 1
                raise

            try:
                result = await _await_native_even_if_cancelled(native)
            except asyncio.CancelledError:
                if native.cancelled() or native.exception() is not None:
                    self._failed += 1
                else:
                    self._completed += 1
                raise
            except BaseException:
                self._failed += 1
                raise
            else:
                self._completed += 1
                return result
            finally:
                self._active -= 1

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=False)


def _resolution_weight(_key: QueryKey, value: QueryResolution) -> int:
    payload = json.dumps(value.rows, ensure_ascii=False, separators=(",", ":"))
    return len(payload.encode("utf-8"))


class AsyncLookupPool:
    def __init__(
        self,
        chatbot: OntologyChatbot,
        *,
        workers: int,
        classification_cache_entries: int = 4096,
        sparql_cache_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        self._chatbot = chatbot
        self._workers = _NativeWorkers(workers)
        self._classifications = BatchSingleFlightCache[str, Classification](
            max_weight=classification_cache_entries,
            weigher=lambda _key, _value: 1,
        )
        self._queries = BatchSingleFlightCache[QueryKey, QueryResolution](
            max_weight=sparql_cache_bytes,
            weigher=_resolution_weight,
        )
        self._closed = False
        self._close_lock = asyncio.Lock()

    @property
    def stats(self) -> LookupStats:
        return LookupStats(
            native=self._workers.stats,
            classifications=self._classifications.stats,
            queries=self._queries.stats,
        )

    async def _classify(
        self, keys: tuple[str, ...]
    ) -> dict[str, Loaded[Classification]]:
        choices = await self._workers.run(self._chatbot.classify_many, keys)
        return {
            key: Loaded(value)
            for key, value in zip(keys, choices, strict=True)
        }

    def _execute_batch(
        self, keys: tuple[QueryKey, ...]
    ) -> dict[QueryKey, Loaded[QueryResolution]]:
        result = {}
        for query, max_rows in keys:
            value = self._chatbot.execute_query(query, max_rows=max_rows)
            result[(query, max_rows)] = Loaded(
                value, cacheable=value.status == "ok"
            )
        return result

    async def _execute(
        self, keys: tuple[QueryKey, ...]
    ) -> dict[QueryKey, Loaded[QueryResolution]]:
        return await self._workers.run(self._execute_batch, keys)

    async def __call__(self, keywords: Sequence[str]) -> str:
        if self._closed:
            raise RuntimeError("lookup pool is closed")
        lookup_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        l1 = CacheOutcome()
        l3 = CacheOutcome()
        prepared = ()
        resolutions: dict[str, QueryResolution] = {}
        rendered = ""
        status = "error"
        try:
            prepared = self._chatbot.prepare_keywords(keywords)
            inputs = [item.model_input for item in prepared]
            choices = await self._classifications.resolve(
                inputs, self._classify, outcome=l1
            )
            keys = list(
                dict.fromkeys(
                    (choice.query, 100) for choice in choices if choice.query is not None
                )
            )
            values = await self._queries.resolve(keys, self._execute, outcome=l3)
            resolutions = {
                query: value
                for (query, _limit), value in zip(keys, values, strict=True)
            }
            rendered = self._chatbot.render_many(prepared, choices, resolutions)
            status = "ok"
            return rendered
        except (QueryGenerationError, SparqlError):
            status = "expected-error"
            raise
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        finally:
            native = self._workers.stats
            logger.info(
                "lookup=%s status=%s keywords=%d l1_hits=%d l1_misses=%d "
                "l1_followers=%d l1_evictions=%d l3_hits=%d l3_misses=%d "
                "l3_followers=%d l3_evictions=%d native_peak=%d rows=%d "
                "rendered_bytes=%d duration_ms=%.1f",
                lookup_id,
                status,
                len(prepared),
                l1.hits,
                l1.misses,
                l1.followers,
                l1.evictions,
                l3.hits,
                l3.misses,
                l3.followers,
                l3.evictions,
                native.peak,
                sum(len(resolution.rows) for resolution in resolutions.values()),
                len(rendered.encode("utf-8")),
                (time.perf_counter() - started) * 1000,
            )

    async def aclose(self) -> None:
        async with self._close_lock:
            if self._workers.closed:
                return
            self._closed = True
            await self._classifications.wait_for_loaders()
            await self._queries.wait_for_loaders()
            self._workers.close()
