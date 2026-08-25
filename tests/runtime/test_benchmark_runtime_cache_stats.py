from __future__ import annotations

import asyncio

from ontchatbot.runtime.cache import BatchSingleFlightCache, Loaded


def test_cache_stats_report_completed_entry_count() -> None:
    """Benchmark gauges need an absolute entry count, not a counter delta."""

    async def exercise() -> int:
        cache = BatchSingleFlightCache[str, str](max_weight=10, weigher=lambda *_: 1)

        async def load(keys):
            return {key: Loaded(key) for key in keys}

        await cache.resolve(["one", "two"], load)
        return cache.stats.entries

    assert asyncio.run(exercise()) == 2
