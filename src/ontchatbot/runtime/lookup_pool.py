"""Bound synchronous ontology lookups without blocking the ASGI event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence


class AsyncLookupPool:
    def __init__(self, lookup: Callable[[Sequence[str] | str], str], *, workers: int):
        if workers < 1:
            raise ValueError("workers must be positive")
        self._lookup = lookup
        self._slots = asyncio.Semaphore(workers)

    async def __call__(self, keywords: Sequence[str] | str) -> str:
        async with self._slots:
            work = asyncio.create_task(asyncio.to_thread(self._lookup, keywords))
            try:
                return await asyncio.shield(work)
            except asyncio.CancelledError:
                # Native ONNX/SPARQL work cannot be stopped by task cancellation.
                while not work.done():
                    try:
                        await asyncio.shield(work)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                raise
