"""Measure bounded local ontology-lookup throughput without an external LLM."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, is_dataclass
import json
import math
from pathlib import Path
import sys
import time
from typing import Any


TICK_SECONDS = 0.01
MAX_LOOP_LAG_SAMPLES = 10_000
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
    """Load non-empty keyword lists from the established JSON workload shape."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid workload: {path}") from exc
    if not isinstance(payload, list):
        raise ValueError("invalid workload: expected a JSON list")

    batches: list[list[str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or "tu_khoa" not in item:
            raise ValueError(f"invalid workload item {index}: expected tu_khoa")
        keywords = item["tu_khoa"]
        if not isinstance(keywords, list) or not all(
            isinstance(keyword, str) for keyword in keywords
        ):
            raise ValueError(f"invalid workload item {index}: tu_khoa must be strings")
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
) -> list[Result]:
    """Run a finite, semaphore-bounded collection of lookup calls."""

    gate = asyncio.Semaphore(concurrency)

    async def one(batch: Sequence[str]) -> Result:
        async with gate:
            return await _one(pool, batch)

    jobs = [batch for _ in range(rounds) for batch in batches]
    return await asyncio.gather(*(one(batch) for batch in jobs))


async def _run_for_duration(
    pool: Lookup,
    batches: Sequence[Sequence[str]],
    *,
    concurrency: int,
    duration: float,
) -> list[Result]:
    """Use a fixed worker set so duration mode cannot create an unbounded task list."""

    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration

    async def worker(worker_number: int) -> list[Result]:
        results: list[Result] = []
        batch_index = worker_number
        while loop.time() < deadline:
            results.append(await _one(pool, batches[batch_index % len(batches)]))
            batch_index += concurrency
        return results

    grouped = await asyncio.gather(*(worker(index) for index in range(concurrency)))
    return [result for results in grouped for result in results]


def _read_rss_kib() -> int | None:
    """Read Linux resident memory without introducing a process-monitor dependency."""

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
    stopped: asyncio.Event,
    *,
    max_samples: int,
) -> tuple[list[float], list[int]]:
    loop = asyncio.get_running_loop()
    lag_samples: list[float] = []
    rss_samples: list[int] = []
    expected = loop.time() + TICK_SECONDS
    while not stopped.is_set() and len(lag_samples) < max_samples:
        await asyncio.sleep(max(0.0, expected - loop.time()))
        observed = loop.time()
        if stopped.is_set():
            break
        lag_samples.append(max(0.0, (observed - expected) * 1000))
        rss = _read_rss_kib()
        if rss is not None:
            rss_samples.append(rss)
        expected += TICK_SECONDS
    return lag_samples, rss_samples


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
    """Run one local benchmark pass and collect only bounded diagnostic samples."""

    if warm:
        await run_workload(pool, batches, concurrency=concurrency, rounds=1)

    started_rss = _read_rss_kib()
    stopped = asyncio.Event()
    max_samples = (
        min(MAX_LOOP_LAG_SAMPLES, math.ceil(duration / TICK_SECONDS))
        if duration is not None
        else MAX_LOOP_LAG_SAMPLES
    )
    monitor = asyncio.create_task(_sample_loop_lag(stopped, max_samples=max_samples))
    started = time.perf_counter()
    try:
        if duration is None:
            results = await run_workload(
                pool, batches, concurrency=concurrency, rounds=rounds
            )
        else:
            results = await _run_for_duration(
                pool, batches, concurrency=concurrency, duration=duration
            )
    finally:
        elapsed = time.perf_counter() - started
        stopped.set()
        lag_samples, sampled_rss = await monitor

    ended_rss = _read_rss_kib()
    rss_values = [
        value for value in (started_rss, *sampled_rss, ended_rss) if value is not None
    ]
    samples = [elapsed_ms for _success, _error, elapsed_ms in results]
    successes = sum(success for success, _error, _elapsed in results)
    errors = Counter(error for success, error, _elapsed in results if not success)
    native, cache = _report_stats(pool)
    return {
        "configuration": configuration,
        "samples": len(samples),
        "successes": successes,
        "errors": dict(sorted(errors.items())),
        "throughput_per_second": successes / elapsed if elapsed else 0.0,
        "latency_ms": summarize_ms(samples),
        "rss_kib": {
            "start": started_rss,
            "peak": max(rss_values) if rss_values else None,
            "end": ended_rss,
        },
        "native": native,
        "cache": cache,
        "event_loop_lag_ms": {
            "samples": len(lag_samples),
            "p95": summarize_ms(lag_samples)["p95"],
        },
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    """Construct exactly one local classifier, chatbot, and shared lookup pool."""

    from ..runtime.lookup_pool import AsyncLookupPool
    from ..runtime.onnx_classifier import OnnxClassifierGenerator
    from ..runtime.pipeline import OntologyChatbot

    batches = load_workload(args.workload)
    generator = OnnxClassifierGenerator.load(
        args.model_dir, intra_op_threads=args.onnx_threads
    )
    chatbot = OntologyChatbot(generator)
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
