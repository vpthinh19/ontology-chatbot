from __future__ import annotations

import asyncio

import pytest

from ontchatbot.runtime.cache import BatchSingleFlightCache, CacheOutcome, Loaded


def test_completed_values_are_lru_evicted_by_weight() -> None:
    calls: list[tuple[str, ...]] = []

    async def exercise() -> None:
        cache = BatchSingleFlightCache[str, str](
            max_weight=2, weigher=lambda _key, _value: 1
        )

        async def load(keys):
            calls.append(keys)
            return {key: Loaded(key.upper()) for key in keys}

        assert await cache.resolve(["a", "b"], load) == ["A", "B"]
        assert await cache.resolve(["a"], load) == ["A"]
        assert await cache.resolve(["c"], load) == ["C"]
        assert await cache.resolve(["b"], load) == ["B"]
        assert cache.stats.evictions == 2

    asyncio.run(exercise())
    assert calls == [("a", "b"), ("c",), ("b",)]


def test_zero_budget_keeps_singleflight_but_no_completed_value() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](
            max_weight=0, weigher=lambda _key, _value: 1
        )

        async def load(keys):
            nonlocal calls
            calls += 1
            await asyncio.sleep(0)
            return {key: Loaded(key) for key in keys}

        assert await asyncio.gather(
            cache.resolve(["x"], load), cache.resolve(["x"], load)
        ) == [["x"], ["x"]]
        assert await cache.resolve(["x"], load) == ["x"]

    asyncio.run(exercise())
    assert calls == 2


def test_fifty_cold_followers_trigger_one_load() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def load(keys):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {key: Loaded("value") for key in keys}

        tasks = [asyncio.create_task(cache.resolve(["same"], load)) for _ in range(50)]
        await entered.wait()
        release.set()
        assert await asyncio.gather(*tasks) == [["value"]] * 50
        assert cache.stats.followers == 49

    asyncio.run(exercise())
    assert calls == 1


def test_each_resolve_records_its_own_singleflight_outcome() -> None:
    async def exercise() -> None:
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)
        entered, release = asyncio.Event(), asyncio.Event()
        outcomes = [CacheOutcome() for _ in range(50)]

        async def load(keys):
            entered.set()
            await release.wait()
            return {key: Loaded("value") for key in keys}

        tasks = [
            asyncio.create_task(cache.resolve(["same"], load, outcome=outcome))
            for outcome in outcomes
        ]
        await entered.wait()
        release.set()
        assert await asyncio.gather(*tasks) == [["value"]] * 50
        assert sum(outcome.hits for outcome in outcomes) == 0
        assert sum(outcome.misses for outcome in outcomes) == 1
        assert sum(outcome.followers for outcome in outcomes) == 49
        assert sum(outcome.evictions for outcome in outcomes) == 0

    asyncio.run(exercise())


def test_loader_failure_is_shared_and_a_later_request_retries() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)

        async def load(keys):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("unavailable")
            return {key: Loaded("ready") for key in keys}

        with pytest.raises(RuntimeError, match="unavailable"):
            await cache.resolve(["key"], load)
        assert await cache.resolve(["key"], load) == ["ready"]

    asyncio.run(exercise())
    assert calls == 2


def test_non_cacheable_value_is_recomputed() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)

        async def load(keys):
            nonlocal calls
            calls += 1
            return {key: Loaded(str(calls), cacheable=False) for key in keys}

        assert await cache.resolve(["key"], load) == ["1"]
        assert await cache.resolve(["key"], load) == ["2"]

    asyncio.run(exercise())
    assert calls == 2


def test_cancelled_follower_does_not_cancel_the_leader_load() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def load(keys):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {key: Loaded("ready") for key in keys}

        leader = asyncio.create_task(cache.resolve(["key"], load))
        await entered.wait()
        follower = asyncio.create_task(cache.resolve(["key"], load))
        await asyncio.sleep(0)
        follower.cancel()
        with pytest.raises(asyncio.CancelledError):
            await follower
        release.set()
        assert await leader == ["ready"]

    asyncio.run(exercise())
    assert calls == 1


def test_cancelled_original_caller_does_not_stop_a_follower() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def load(keys):
            nonlocal calls
            calls += 1
            entered.set()
            await release.wait()
            return {key: Loaded("ready") for key in keys}

        original = asyncio.create_task(cache.resolve(["key"], load))
        await entered.wait()
        follower = asyncio.create_task(cache.resolve(["key"], load))
        await asyncio.sleep(0)
        original.cancel()
        with pytest.raises(asyncio.CancelledError):
            await original
        release.set()
        assert await follower == ["ready"]

    asyncio.run(exercise())
    assert calls == 1


def test_duplicate_input_keys_preserve_output_order() -> None:
    calls: list[tuple[str, ...]] = []

    async def exercise() -> None:
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)

        async def load(keys):
            calls.append(keys)
            return {"first": Loaded("one"), "second": Loaded("two")}

        assert await cache.resolve(["second", "first", "second"], load) == [
            "two",
            "one",
            "two",
        ]

    asyncio.run(exercise())
    assert calls == [("second", "first")]


def test_oversized_completed_value_is_returned_but_not_retained() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](
            max_weight=2, weigher=lambda _key, value: len(value)
        )

        async def load(keys):
            nonlocal calls
            calls += 1
            return {key: Loaded("oversized") for key in keys}

        assert await cache.resolve(["key"], load) == ["oversized"]
        assert cache.stats.current_weight == 0
        assert await cache.resolve(["key"], load) == ["oversized"]

    asyncio.run(exercise())
    assert calls == 2


def test_negative_weight_is_rejected_without_caching_the_value() -> None:
    async def exercise() -> None:
        cache = BatchSingleFlightCache[str, str](max_weight=1, weigher=lambda *_: -1)

        async def load(keys):
            return {key: Loaded("value") for key in keys}

        with pytest.raises(ValueError, match="weights must be non-negative"):
            await cache.resolve(["key"], load)
        assert cache.stats.current_weight == 0

    asyncio.run(exercise())


def test_invalid_weight_does_not_partially_cache_a_batch() -> None:
    calls = 0

    async def exercise() -> None:
        nonlocal calls
        cache = BatchSingleFlightCache[str, str](
            max_weight=10,
            weigher=lambda key, _value: -1 if key == "bad" else 1,
        )

        async def load(keys):
            nonlocal calls
            calls += 1
            return {key: Loaded("value") for key in keys}

        with pytest.raises(ValueError, match="weights must be non-negative"):
            await cache.resolve(["good", "bad"], load)
        assert await cache.resolve(["good"], load) == ["value"]

    asyncio.run(exercise())
    assert calls == 2


def test_cancelling_wait_for_loaders_does_not_cancel_a_shared_loader() -> None:
    async def exercise() -> None:
        cache = BatchSingleFlightCache[str, str](max_weight=1, weigher=lambda *_: 1)
        entered, release = asyncio.Event(), asyncio.Event()

        async def load(keys):
            entered.set()
            await release.wait()
            return {key: Loaded("value") for key in keys}

        request = asyncio.create_task(cache.resolve(["key"], load))
        await entered.wait()
        waiting = asyncio.create_task(cache.wait_for_loaders())
        await asyncio.sleep(0)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        release.set()
        assert await request == ["value"]
        await cache.wait_for_loaders()

    asyncio.run(exercise())
