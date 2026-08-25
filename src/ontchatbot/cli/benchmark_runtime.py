"""Measure bounded local ontology-lookup throughput without an external LLM."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, field, is_dataclass
import heapq
import json
import math
from pathlib import Path
import sys
import time
from typing import Any


TICK_SECONDS = 0.01
MAX_LATENCY_SAMPLES = 4096
MAX_LOOP_LAG_SAMPLES = 4096
Lookup = Callable[[Sequence[str]], Awaitable[str]]
Result = tuple[bool, str | None, float]


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--onnx-threads", type=_positive_int, default=1)
    parser.add_argument("--lookup-workers", type=_positive_int, default=8)
    parser.add_argument("--concurrency", type=_positive_int, default=1)
    parser.add_argument("--rounds", type=_positive_int, default=1)
    parser.add_argument("--warm", action="store_true")
    parser.add_argument("--duration", type=_positive_float)
    return parser.parse_args(argv)


def load_workload(path: Path) -> list[list[str]]:
    """Load non-empty, non-blank keyword lists from the established JSON shape."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid workload: {path}") from exc
    if not isinstance(payload, list):
        raise ValueError("invalid workload: expected a JSON list")

    batches: list[list[str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or "tu_khoa" not in item:
            raise ValueError(f"invalid workload item {index}: expected tu_khoa")
        keywords = item["tu_khoa"]
        if not isinstance(keywords, list) or not all(
            isinstance(keyword, str) and keyword.strip() for keyword in keywords
        ):
            raise ValueError(
                f"invalid workload item {index}: tu_khoa must be non-blank strings"
            )
        if keywords:
            batches.append(keywords)
    if not batches:
        raise ValueError("invalid workload: no non-empty tu_khoa lists")
    return batches


def summarize_ms(samples: Sequence[float]) -> dict[str, float | None]:
    """Summarize observations using nearest-rank percentiles."""

    if not samples:
        return {"p50": None, "p95": None, "p99": None}
    ordered = sorted(samples)
    return {
        f"p{percentile}": ordered[math.ceil(len(ordered) * percentile / 100) - 1]
        for percentile in (50, 95, 99)
    }


def _sample_priority(request_id: int) -> int:
    """Produce a deterministic, well-distributed priority for a request identity."""

    value = (request_id + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return value ^ (value >> 31)


class _BoundedReservoir:
    """Keep a deterministic bounded subset while still counting every observation."""

    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._heap: list[tuple[int, float]] = []
        self.total = 0

    def add(self, value: float, *, request_id: int) -> None:
        priority = _sample_priority(request_id)
        self.total += 1
        item = (-priority, value)
        if len(self._heap) < self._capacity:
            heapq.heappush(self._heap, item)
        elif item[0] > self._heap[0][0]:
            heapq.heapreplace(self._heap, item)

    @property
    def samples(self) -> list[float]:
        return [value for _priority, value in self._heap]

    def __len__(self) -> int:
        return len(self._heap)


@dataclass
class _OutcomeSummary:
    latency: _BoundedReservoir = field(
        default_factory=lambda: _BoundedReservoir(MAX_LATENCY_SAMPLES)
    )
    successes: int = 0
    errors: Counter[str] = field(default_factory=Counter)

    @property
    def samples(self) -> int:
        return self.latency.total

    def record(self, result: Result, *, request_id: int) -> None:
        success, error, elapsed_ms = result
        self.latency.add(elapsed_ms, request_id=request_id)
        if success:
            self.successes += 1
        else:
            assert error is not None
            self.errors[error] += 1


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


async def _one(pool: Lookup, batch: Sequence[str]) -> Result:
    started = time.perf_counter()
    try:
        await pool(batch)
    except Exception as exc:
        return False, type(exc).__name__, _elapsed_ms(started)
    return True, None, _elapsed_ms(started)


async def run_workload(
    pool: Lookup,
    batches: Sequence[Sequence[str]],
    *,
    concurrency: int,
    rounds: int,
    summary: _OutcomeSummary | None = None,
) -> _OutcomeSummary:
    """Run finite work through a fixed worker set rather than per-request tasks."""

    outcomes = summary or _OutcomeSummary()
    total_jobs = rounds * len(batches)
    next_job = 0

    async def worker() -> None:
        nonlocal next_job
        while next_job < total_jobs:
            job = next_job
            next_job += 1
            outcomes.record(
                await _one(pool, batches[job % len(batches)]), request_id=job
            )

    await asyncio.gather(*(worker() for _ in range(concurrency)))
    return outcomes


async def _run_for_duration(
    pool: Lookup,
    batches: Sequence[Sequence[str]],
    *,
    concurrency: int,
    duration: float,
    summary: _OutcomeSummary,
) -> None:
    """Cycle fixed workers until the deadline without retaining per-request output."""

    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration

    async def worker(worker_number: int) -> None:
        batch_index = worker_number
        request_number = 0
        while loop.time() < deadline:
            summary.record(
                await _one(pool, batches[batch_index % len(batches)]),
                request_id=request_number * concurrency + worker_number,
            )
            batch_index += concurrency
            request_number += 1

    await asyncio.gather(*(worker(index) for index in range(concurrency)))


def _read_rss_kib() -> int | None:
    """Read Linux resident memory without a process-monitor dependency."""

    if sys.platform != "linux":
        return None
    try:
        for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except (OSError, IndexError, ValueError):
        return None
    return None


async def _sample_loop_lag(
    stopped: asyncio.Event, armed: asyncio.Event
) -> tuple[_BoundedReservoir, int | None]:
    """Monitor until stopped, retaining a bounded lag reservoir and RSS peak."""

    loop = asyncio.get_running_loop()
    lag = _BoundedReservoir(MAX_LOOP_LAG_SAMPLES)
    rss_peak: int | None = None
    expected = loop.time() + TICK_SECONDS
    armed.set()
    while True:
        await asyncio.sleep(max(0.0, expected - loop.time()))
        observed = loop.time()
        lag.add(max(0.0, (observed - expected) * 1000), request_id=lag.total)
        rss = _read_rss_kib()
        if rss is not None:
            rss_peak = rss if rss_peak is None else max(rss_peak, rss)
        if stopped.is_set():
            return lag, rss_peak
        expected = observed + TICK_SECONDS


def _stats_mapping(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return dict(vars(value))


def _report_stats(pool: Any) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    stats = pool.stats
    return (
        _stats_mapping(stats.native),
        {
            "classifications": _stats_mapping(stats.classifications),
            "queries": _stats_mapping(stats.queries),
        },
    )


_NATIVE_COUNTERS = ("submitted", "completed", "failed", "worker_wait_ms")
_CACHE_COUNTERS = ("hits", "misses", "followers", "loads", "evictions")


def _counter_deltas(
    current: dict[str, Any], baseline: dict[str, Any], fields: Sequence[str]
) -> dict[str, Any]:
    return {field: current[field] - baseline[field] for field in fields}


def _native_stats(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        **_counter_deltas(current, baseline, _NATIVE_COUNTERS),
        "active": current["active"],
        "lifetime_peak": current["peak"],
        "baseline_peak": baseline["peak"],
    }


def _cache_stats(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        **_counter_deltas(current, baseline, _CACHE_COUNTERS),
        "entries": current["entries"],
        "current_weight": current["current_weight"],
    }


async def run_benchmark(
    pool: Lookup,
    batches: Sequence[Sequence[str]],
    *,
    concurrency: int,
    rounds: int,
    warm: bool,
    duration: float | None,
    configuration: dict[str, Any],
) -> dict[str, Any]:
    """Run one local benchmark pass with constant-memory scheduling and telemetry."""

    if warm:
        await run_workload(pool, batches, concurrency=concurrency, rounds=1)
    baseline_native, baseline_cache = _report_stats(pool)

    started_rss = _read_rss_kib()
    stopped = asyncio.Event()
    armed = asyncio.Event()
    monitor = asyncio.create_task(_sample_loop_lag(stopped, armed))
    await armed.wait()
    outcomes = _OutcomeSummary()
    started = time.perf_counter()
    try:
        if duration is None:
            await run_workload(
                pool,
                batches,
                concurrency=concurrency,
                rounds=rounds,
                summary=outcomes,
            )
        else:
            await _run_for_duration(
                pool,
                batches,
                concurrency=concurrency,
                duration=duration,
                summary=outcomes,
            )
    finally:
        elapsed = time.perf_counter() - started
        stopped.set()
        lag, sampled_rss_peak = await monitor

    ended_rss = _read_rss_kib()
    rss_values = [
        value
        for value in (started_rss, sampled_rss_peak, ended_rss)
        if value is not None
    ]
    native, cache = _report_stats(pool)
    latency = summarize_ms(outcomes.latency.samples)
    return {
        "configuration": configuration,
        "samples": outcomes.samples,
        "successes": outcomes.successes,
        "errors": dict(sorted(outcomes.errors.items())),
        "throughput_per_second": outcomes.successes / elapsed if elapsed else 0.0,
        "latency_ms": {"retained_samples": len(outcomes.latency), **latency},
        "rss_kib": {
            "start": started_rss,
            "peak": max(rss_values) if rss_values else None,
            "end": ended_rss,
        },
        "native": _native_stats(native, baseline_native),
        "cache": {
            key: _cache_stats(value, baseline_cache[key])
            for key, value in cache.items()
        },
        "event_loop_lag_ms": {
            "samples": lag.total,
            "p95": summarize_ms(lag.samples)["p95"],
        },
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    """Construct exactly one graph, classifier, chatbot, and shared lookup pool."""

    from ..runtime.lookup_pool import AsyncLookupPool
    from ..runtime.onnx_classifier import OnnxClassifierGenerator
    from ..runtime.pipeline import OntologyChatbot
    from ..runtime.sparql import load_ontology

    batches = load_workload(args.workload)
    graph = load_ontology()
    generator = OnnxClassifierGenerator.load(
        args.model_dir, graph=graph, intra_op_threads=args.onnx_threads
    )
    chatbot = OntologyChatbot(generator, graph=graph)
    pool = AsyncLookupPool(chatbot, workers=args.lookup_workers)
    try:
        return await run_benchmark(
            pool,
            batches,
            concurrency=args.concurrency,
            rounds=args.rounds,
            warm=args.warm,
            duration=args.duration,
            configuration={
                "model_dir": str(args.model_dir),
                "workload": str(args.workload),
                "onnx_threads": args.onnx_threads,
                "lookup_workers": args.lookup_workers,
                "concurrency": args.concurrency,
                "rounds": args.rounds,
                "warm": args.warm,
                "duration_seconds": args.duration,
            },
        )
    finally:
        await pool.aclose()


def main() -> None:
    args = _parse_args()
    report = asyncio.run(_run(args))
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
