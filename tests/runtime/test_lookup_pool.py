from __future__ import annotations

import asyncio
import threading
import time

import httpx
import pytest

from ontchatbot.runtime.api import create_app
from ontchatbot.runtime.lookup_pool import AsyncLookupPool


def test_pool_never_runs_more_than_four_lookups_at_once() -> None:
    live = 0
    peak = 0
    lock = threading.Lock()

    def lookup(value):
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        try:
            time.sleep(0.02)
            return str(value)
        finally:
            with lock:
                live -= 1

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=4)
        return await asyncio.gather(*(pool([str(i)]) for i in range(12)))

    assert len(asyncio.run(exercise())) == 12
    assert peak == 4


def test_a_blocked_lookup_does_not_block_the_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()

    def lookup(_):
        started.set()
        release.wait(timeout=1)
        return "xong"

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=1)
        task = asyncio.create_task(pool(["học phí"]))
        while not started.is_set():
            await asyncio.sleep(0)
        transport = httpx.ASGITransport(app=create_app(object()))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await asyncio.wait_for(client.get("/healthz"), timeout=0.05)
        release.set()
        return response, await task

    response, result = asyncio.run(exercise())
    assert response.json() == {"status": "ok"}
    assert result == "xong"


def test_an_exception_releases_the_lookup_slot() -> None:
    calls = 0

    def lookup(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("hỏng")
        return "xong"

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=1)
        with pytest.raises(RuntimeError, match="hỏng"):
            await pool(["một"])
        return await asyncio.wait_for(pool(["hai"]), timeout=0.2)

    assert asyncio.run(exercise()) == "xong"


def test_cancellation_holds_the_slot_until_native_work_finishes() -> None:
    first_started = threading.Event()
    first_release = threading.Event()
    second_started = threading.Event()

    def lookup(keywords):
        if keywords == ["một"]:
            first_started.set()
            first_release.wait(timeout=1)
        else:
            second_started.set()
        return "xong"

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=1)
        first = asyncio.create_task(pool(["một"]))
        while not first_started.is_set():
            await asyncio.sleep(0)
        first.cancel()
        second = asyncio.create_task(pool(["hai"]))
        await asyncio.sleep(0.02)
        assert not second_started.is_set()
        first_release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await asyncio.wait_for(second, timeout=0.2) == "xong"

    asyncio.run(exercise())


@pytest.mark.parametrize("workers", [0, -1])
def test_pool_rejects_non_positive_worker_counts(workers) -> None:
    with pytest.raises(ValueError, match="workers must be positive"):
        AsyncLookupPool(str, workers=workers)
