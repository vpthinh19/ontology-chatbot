"""Event-loop-owned weighted caches with batched singleflight loading."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass(frozen=True)
class Loaded(Generic[V]):
    value: V
    cacheable: bool = True


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    followers: int
    loads: int
    evictions: int
    current_weight: int


@dataclass(frozen=True)
class CacheOutcome:
    """Immutable cache decisions attributable to one resolve call."""

    hits: int = 0
    misses: int = 0
    followers: int = 0
    evictions: int = 0


class CacheOutcomeRecorder:
    """Event-loop-local mutable recorder that exposes immutable snapshots."""

    def __init__(self) -> None:
        self._hits = 0
        self._misses = 0
        self._followers = 0
        self._evictions = 0

    @property
    def snapshot(self) -> CacheOutcome:
        return CacheOutcome(
            hits=self._hits,
            misses=self._misses,
            followers=self._followers,
            evictions=self._evictions,
        )

    def record_hit(self) -> None:
        self._hits += 1

    def record_miss(self) -> None:
        self._misses += 1

    def record_follower(self) -> None:
        self._followers += 1

    def record_evictions(self, count: int) -> None:
        self._evictions += count


@dataclass(frozen=True)
class _Published(Generic[V]):
    value: V
    evictions: int


Loader = Callable[[tuple[K, ...]], Awaitable[Mapping[K, Loaded[V]]]]


class BatchSingleFlightCache(Generic[K, V]):
    def __init__(self, *, max_weight: int, weigher: Callable[[K, V], int]):
        if max_weight < 0:
            raise ValueError("max_weight must be non-negative")
        self._max_weight = max_weight
        self._weigher = weigher
        self._completed: OrderedDict[K, tuple[V, int]] = OrderedDict()
        self._inflight: dict[K, asyncio.Future[_Published[V]]] = {}
        self._loaders: set[asyncio.Task[None]] = set()
        self._hits = self._misses = self._followers = 0
        self._loads = self._evictions = self._weight = 0

    @property
    def stats(self) -> CacheStats:
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            followers=self._followers,
            loads=self._loads,
            evictions=self._evictions,
            current_weight=self._weight,
        )

    def _remember(self, key: K, value: V, *, weight: int) -> int:
        if weight < 0:
            raise ValueError("cache weights must be non-negative")
        if self._max_weight == 0 or weight > self._max_weight:
            return 0

        previous = self._completed.pop(key, None)
        if previous is not None:
            self._weight -= previous[1]
        self._completed[key] = (value, weight)
        self._weight += weight

        evictions = 0
        while self._weight > self._max_weight:
            _evicted_key, (_evicted_value, evicted_weight) = self._completed.popitem(
                last=False
            )
            self._weight -= evicted_weight
            self._evictions += 1
            evictions += 1
        return evictions

    async def resolve(
        self,
        keys: Iterable[K],
        loader: Loader[K, V],
        *,
        outcome: CacheOutcomeRecorder | None = None,
    ) -> list[V]:
        ordered = list(keys)
        unique = list(dict.fromkeys(ordered))
        pending: dict[K, asyncio.Future[_Published[V]]] = {}
        leaders: list[K] = []
        loop = asyncio.get_running_loop()

        for key in unique:
            completed = self._completed.get(key)
            if completed is not None:
                self._hits += 1
                if outcome is not None:
                    outcome.record_hit()
                self._completed.move_to_end(key)
                future = loop.create_future()
                future.set_result(_Published(completed[0], 0))
            elif key in self._inflight:
                self._followers += 1
                if outcome is not None:
                    outcome.record_follower()
                future = self._inflight[key]
            else:
                self._misses += 1
                if outcome is not None:
                    outcome.record_miss()
                future = loop.create_future()
                future.add_done_callback(_consume_exception)
                self._inflight[key] = future
                leaders.append(key)
            pending[key] = future

        if leaders:
            task = asyncio.create_task(self._publish(tuple(leaders), loader))
            self._loaders.add(task)
            task.add_done_callback(self._loaders.discard)

        published = await asyncio.gather(
            *(asyncio.shield(pending[key]) for key in unique)
        )
        by_key = dict(zip(unique, published, strict=True))
        if outcome is not None:
            outcome.record_evictions(sum(by_key[key].evictions for key in leaders))
        return [by_key[key].value for key in ordered]

    async def _publish(
        self,
        keys: tuple[K, ...],
        loader: Loader[K, V],
    ) -> None:
        self._loads += 1
        try:
            loaded = await loader(keys)
            if set(loaded) != set(keys):
                raise ValueError("loader must return exactly one value for every key")
            results: list[tuple[K, Loaded[V], int | None]] = []
            for key in keys:
                result = loaded[key]
                if not isinstance(result, Loaded):
                    raise TypeError("loader values must be Loaded instances")
                weight = self._weigher(key, result.value) if result.cacheable else None
                if weight is not None and weight < 0:
                    raise ValueError("cache weights must be non-negative")
                results.append((key, result, weight))

            published: list[tuple[K, Loaded[V], int]] = []
            for key, result, weight in results:
                evictions = 0
                if result.cacheable:
                    assert weight is not None
                    evictions = self._remember(key, result.value, weight=weight)
                published.append((key, result, evictions))

            for key, result, evictions in published:
                future = self._inflight[key]
                if not future.done():
                    future.set_result(_Published(result.value, evictions))
        except BaseException as error:
            for key in keys:
                future = self._inflight[key]
                if not future.done():
                    future.set_exception(error)
        finally:
            for key in keys:
                self._inflight.pop(key, None)

    async def wait_for_loaders(self) -> None:
        while self._loaders:
            await asyncio.gather(
                *(asyncio.shield(task) for task in tuple(self._loaders)),
                return_exceptions=True,
            )


def _consume_exception(future: asyncio.Future[object]) -> None:
    if future.done() and not future.cancelled():
        future.exception()
