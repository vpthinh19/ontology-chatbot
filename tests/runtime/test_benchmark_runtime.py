from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ontchatbot.cli import benchmark_runtime
from ontchatbot.cli.benchmark_runtime import (
    MAX_LATENCY_SAMPLES,
    _BoundedReservoir,
    _parse_args,
    _run,
    _sample_loop_lag,
    load_workload,
    run_benchmark,
    run_workload,
    summarize_ms,
)


def test_load_workload_keeps_non_empty_keyword_batches(tmp_path) -> None:
    """Dropping empty requests prevents benchmark samples that never hit lookup."""
    path = tmp_path / "workload.json"
    path.write_text(
        json.dumps(
            [
                {"tu_khoa": ["bảo lưu", "nghỉ học tạm thời"]},
                {"tu_khoa": []},
                {"tu_khoa": ["học phí"]},
            ]
        ),
        encoding="utf-8",
    )

    assert load_workload(path) == [
        ["bảo lưu", "nghỉ học tạm thời"],
        ["học phí"],
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {"tu_khoa": ["học phí"]},
        [{"tu_khoa": "học phí"}],
        [{"khac": ["học phí"]}],
        [{"tu_khoa": ["học phí", 3]}],
        [{"tu_khoa": []}],
    ],
)
def test_load_workload_rejects_invalid_shapes(tmp_path, payload) -> None:
    """Malformed workload files must not produce a misleading zero-request run."""
    path = tmp_path / "workload.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="workload"):
        load_workload(path)


def test_load_workload_rejects_blank_keywords(tmp_path) -> None:
    """A blank keyword would fail outside the measured lookup contract."""
    path = tmp_path / "workload.json"
    path.write_text(json.dumps([{"tu_khoa": ["học phí", " "]}]), encoding="utf-8")

    with pytest.raises(ValueError, match="workload"):
        load_workload(path)


def test_load_workload_wraps_invalid_utf8_as_a_validation_error(tmp_path) -> None:
    """A malformed byte stream must be reported as workload validation, not a codec leak."""
    path = tmp_path / "workload.json"
    path.write_bytes(b"[\xff]")

    with pytest.raises(ValueError, match="invalid workload"):
        load_workload(path)


def test_percentiles_use_nearest_rank() -> None:
    """The report must not interpolate away an observed tail latency."""
    assert summarize_ms([1.0, 2.0, 3.0, 100.0]) == {
        "p50": 2.0,
        "p95": 100.0,
        "p99": 100.0,
    }


@pytest.mark.parametrize(
    "flag, value",
    [
        ("--onnx-threads", "0"),
        ("--lookup-workers", "0"),
        ("--concurrency", "0"),
        ("--rounds", "0"),
        ("--duration", "0"),
    ],
)
def test_parse_args_rejects_non_positive_limits(flag, value) -> None:
    """A zero limit would either deadlock scheduling or hide invalid configuration."""
    with pytest.raises(SystemExit):
        _parse_args(
            [
                "--model-dir",
                "model",
                "--workload",
                "workload.json",
                flag,
                value,
            ]
        )


@dataclass(frozen=True)
class _NativeStats:
    submitted: int = 3
    active: int = 0
    peak: int = 2
    completed: int = 3
    failed: int = 0
    worker_wait_ms: float = 0.0


@dataclass(frozen=True)
class _CacheStats:
    hits: int = 1
    misses: int = 2
    followers: int = 0
    loads: int = 0
    evictions: int = 0
    entries: int = 2
    current_weight: int = 2


@dataclass(frozen=True)
class _LookupStats:
    native: _NativeStats = _NativeStats()
    classifications: _CacheStats = _CacheStats()
    queries: _CacheStats = _CacheStats()


class _FakeLookup:
    stats = _LookupStats()

    async def __call__(self, keywords: list[str]) -> str:
        if keywords == ["fails"]:
            raise RuntimeError("expected fake failure")
        await asyncio.sleep(0)
        return "ok"


class _CountingLookup:
    def __init__(self) -> None:
        self.calls = 0
        self.stats = SimpleNamespace(
            native=SimpleNamespace(
                submitted=0,
                active=0,
                peak=0,
                completed=0,
                failed=0,
                worker_wait_ms=0.0,
            ),
            classifications=SimpleNamespace(
                hits=0,
                misses=0,
                followers=0,
                loads=0,
                evictions=0,
                entries=0,
                current_weight=0,
            ),
            queries=SimpleNamespace(
                hits=0,
                misses=0,
                followers=0,
                loads=0,
                evictions=0,
                entries=0,
                current_weight=0,
            ),
        )

    async def __call__(self, _keywords: list[str]) -> str:
        self.calls += 1
        native = self.stats.native
        native.submitted += 1
        native.completed += 1
        self.stats.classifications.hits += 1
        self.stats.queries.hits += 1
        await asyncio.sleep(0)
        return "ok"


def test_report_contains_runtime_metrics_for_a_fake_lookup() -> None:
    """The CLI report must expose all operational metrics without an ONNX model."""
    report = asyncio.run(
        run_benchmark(
            _FakeLookup(),
            [["works"], ["fails"]],
            concurrency=2,
            rounds=1,
            warm=False,
            duration=None,
            configuration={"onnx_threads": 1, "lookup_workers": 2},
        )
    )

    assert set(report) == {
        "configuration",
        "samples",
        "successes",
        "errors",
        "throughput_per_second",
        "latency_ms",
        "rss_kib",
        "native",
        "cache",
        "event_loop_lag_ms",
    }
    assert report["samples"] == 2
    assert report["successes"] == 1
    assert report["errors"] == {"RuntimeError": 1}
    assert report["latency_ms"].keys() == {
        "retained_samples",
        "p50",
        "p95",
        "p99",
    }
    assert report["native"]["active"] == 0
    assert report["native"]["lifetime_peak"] == 2
    assert report["native"]["baseline_peak"] == 2
    assert report["cache"]["classifications"]["hits"] == 0
    assert report["cache"]["classifications"]["entries"] == 2
    assert report["cache"]["classifications"]["current_weight"] == 2
    assert report["event_loop_lag_ms"].keys() == {"samples", "p95"}


def test_latency_reservoir_selects_same_request_ids_regardless_of_completion_order() -> None:
    """Concurrent completion order must not change the retained latency sample."""
    requests = [(11, 1.0), (12, 2.0), (13, 3.0), (14, 4.0)]
    first = _BoundedReservoir(2)
    second = _BoundedReservoir(2)
    for request_id, latency in requests:
        first.add(latency, request_id=request_id)
    for request_id, latency in reversed(requests):
        second.add(latency, request_id=request_id)

    assert sorted(first.samples) == sorted(second.samples)


def test_rounds_mode_keeps_pending_tasks_to_the_requested_concurrency() -> None:
    """Large finite runs must not create one waiting coroutine per request."""

    class BlockingLookup:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def __call__(self, _keywords) -> str:
            self.started.set()
            await self.release.wait()
            return "ok"

    async def exercise() -> None:
        lookup = BlockingLookup()
        task = asyncio.create_task(
            run_workload(
                lookup,
                [["học phí"]],
                concurrency=2,
                rounds=MAX_LATENCY_SAMPLES * 2,
            )
        )
        try:
            await asyncio.wait_for(lookup.started.wait(), timeout=1)
            pending = [
                candidate
                for candidate in asyncio.all_tasks()
                if candidate is not asyncio.current_task() and not candidate.done()
            ]
            assert len(pending) < 20
        finally:
            lookup.release.set()
            await task

    asyncio.run(exercise())


def test_duration_mode_reports_total_but_retains_only_bounded_latency_samples(
    monkeypatch,
) -> None:
    """An hour-long fast run must not retain one tuple or latency per lookup."""
    monkeypatch.setattr(benchmark_runtime, "MAX_LATENCY_SAMPLES", 3)
    report = asyncio.run(
        run_benchmark(
            _FakeLookup(),
            [["works"]],
            concurrency=2,
            rounds=1,
            warm=False,
            duration=0.03,
            configuration={},
        )
    )

    assert report["samples"] > 3
    assert report["latency_ms"]["retained_samples"] == 3


def test_loop_lag_monitor_runs_past_its_retained_sample_cap(monkeypatch) -> None:
    """A bounded reservoir must not stop monitoring a long duration run."""
    monkeypatch.setattr(benchmark_runtime, "MAX_LOOP_LAG_SAMPLES", 2)
    monkeypatch.setattr(benchmark_runtime, "TICK_SECONDS", 0.001)

    async def exercise():
        stopped = asyncio.Event()
        armed = asyncio.Event()
        task = asyncio.create_task(_sample_loop_lag(stopped, armed))
        await armed.wait()
        await asyncio.sleep(0.008)
        stopped.set()
        return await task

    lag, _peak_rss = asyncio.run(exercise())
    assert lag.total > 2
    assert len(lag.samples) == 2


def test_loop_lag_monitor_records_the_final_tick_after_stop(monkeypatch) -> None:
    """The final delayed tick captures lag that arrives as the benchmark ends."""
    monkeypatch.setattr(benchmark_runtime, "TICK_SECONDS", 0.001)

    async def exercise():
        stopped = asyncio.Event()
        armed = asyncio.Event()
        task = asyncio.create_task(_sample_loop_lag(stopped, armed))
        await armed.wait()
        await asyncio.sleep(0)
        stopped.set()
        return await task

    lag, _peak_rss = asyncio.run(exercise())
    assert lag.total == 1


def test_warm_stats_are_excluded_from_the_timed_report() -> None:
    """Warm-up loads must not masquerade as timed native/cache activity."""
    lookup = _CountingLookup()
    report = asyncio.run(
        run_benchmark(
            lookup,
            [["học phí"]],
            concurrency=1,
            rounds=1,
            warm=True,
            duration=None,
            configuration={},
        )
    )

    assert lookup.calls == 2
    assert report["native"]["submitted"] == 1
    assert report["cache"]["classifications"]["hits"] == 1


def test_timed_stats_keep_gauges_absolute_after_a_warm_failure() -> None:
    """Warm counters are excluded while the timed failed lookup remains observable."""

    class FailingLookup:
        def __init__(self) -> None:
            self.stats = SimpleNamespace(
                native=SimpleNamespace(
                    submitted=0,
                    active=0,
                    peak=0,
                    completed=0,
                    failed=0,
                    worker_wait_ms=0.0,
                ),
                classifications=SimpleNamespace(
                    hits=0,
                    misses=0,
                    followers=0,
                    loads=0,
                    evictions=0,
                    entries=0,
                    current_weight=0,
                ),
                queries=SimpleNamespace(
                    hits=0,
                    misses=0,
                    followers=0,
                    loads=0,
                    evictions=0,
                    entries=0,
                    current_weight=0,
                ),
            )

        async def __call__(self, _keywords) -> str:
            native = self.stats.native
            native.submitted += 1
            native.active += 1
            native.peak = max(native.peak, native.active)
            self.stats.classifications.misses += 1
            native.failed += 1
            native.active -= 1
            raise RuntimeError("expected")

    report = asyncio.run(
        run_benchmark(
            FailingLookup(),
            [["học phí"]],
            concurrency=1,
            rounds=1,
            warm=True,
            duration=None,
            configuration={},
        )
    )

    assert report["native"] == {
        "submitted": 1,
        "active": 0,
        "lifetime_peak": 1,
        "baseline_peak": 1,
        "completed": 0,
        "failed": 1,
        "worker_wait_ms": 0.0,
    }
    assert report["cache"]["classifications"]["misses"] == 1
    assert report["cache"]["classifications"]["entries"] == 0


def test_runtime_setup_shares_one_graph_and_closes_the_pool_on_failure(
    tmp_path, monkeypatch
) -> None:
    """Construction failures after pool creation must release the sole local worker pool."""
    from ontchatbot.runtime import lookup_pool, onnx_classifier, pipeline, sparql

    workload = tmp_path / "workload.json"
    workload.write_text(json.dumps([{"tu_khoa": ["học phí"]}]), encoding="utf-8")
    graph = object()
    received_graphs = []

    class Pool:
        def __init__(self, *_args, **_kwargs) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    pool = Pool()

    def load_generator(_cls, _model_dir, *, graph, intra_op_threads):
        received_graphs.append((graph, intra_op_threads))
        return "generator"

    def make_chatbot(generator, *, graph):
        received_graphs.append((generator, graph))
        return "chatbot"

    async def explode(*_args, **_kwargs):
        raise RuntimeError("benchmark failure")

    monkeypatch.setattr(sparql, "load_ontology", lambda: graph)
    monkeypatch.setattr(
        onnx_classifier.OnnxClassifierGenerator, "load", classmethod(load_generator)
    )
    monkeypatch.setattr(pipeline, "OntologyChatbot", make_chatbot)
    monkeypatch.setattr(lookup_pool, "AsyncLookupPool", lambda *_args, **_kwargs: pool)
    monkeypatch.setattr(benchmark_runtime, "run_benchmark", explode)

    args = SimpleNamespace(
        workload=workload,
        model_dir=Path("model"),
        onnx_threads=2,
        lookup_workers=3,
        concurrency=1,
        rounds=1,
        warm=False,
        duration=None,
    )
    with pytest.raises(RuntimeError, match="benchmark failure"):
        asyncio.run(_run(args))

    assert received_graphs == [(graph, 2), ("generator", graph)]
    assert pool.closed


def test_armed_monitor_observes_a_synchronously_blocking_lookup(monkeypatch) -> None:
    """The monitor is armed before a no-yield lookup can monopolize the loop."""
    import time

    monkeypatch.setattr(benchmark_runtime, "TICK_SECONDS", 0.001)
    observed_rss = []

    def read_rss() -> int:
        observed_rss.append(True)
        return 777

    monkeypatch.setattr(benchmark_runtime, "_read_rss_kib", read_rss)
    original_monitor = benchmark_runtime._sample_loop_lag

    class BlockingLookup:
        stats = _LookupStats()
        calls = 0

        async def __call__(self, _keywords) -> str:
            self.calls += 1
            time.sleep(0.015)
            return "ok"

    lookup = BlockingLookup()

    async def checked_monitor(stopped, armed):
        assert lookup.calls == 0
        return await original_monitor(stopped, armed)

    monkeypatch.setattr(benchmark_runtime, "_sample_loop_lag", checked_monitor)
    report = asyncio.run(
        run_benchmark(
            lookup,
            [["học phí"]],
            concurrency=1,
            rounds=1,
            warm=False,
            duration=None,
            configuration={},
        )
    )

    assert lookup.calls == 1
    assert observed_rss
    assert report["rss_kib"]["peak"] == 777
    assert report["event_loop_lag_ms"]["samples"] >= 1


def test_help_parser_is_lazy_about_onnx_in_a_clean_process() -> None:
    """Help must remain available even when the optional ONNX runtime is absent."""
    import subprocess
    import sys

    command = [
        sys.executable,
        "-c",
        (
            "import sys; from ontchatbot.cli.benchmark_runtime import _parse_args; "
            "\ntry: _parse_args(['--help'])\nexcept SystemExit: pass\n"
            "assert 'onnxruntime' not in sys.modules"
        ),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
