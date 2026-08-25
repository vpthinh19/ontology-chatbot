from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json

import pytest

from ontchatbot.cli.benchmark_runtime import (
    _parse_args,
    load_workload,
    run_benchmark,
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
    evictions: int = 0
    size: int = 2
    weight: int = 2


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
    assert report["latency_ms"].keys() == {"p50", "p95", "p99"}
    assert report["native"]["peak"] == 2
    assert report["cache"]["classifications"]["hits"] == 1
    assert report["event_loop_lag_ms"].keys() == {"samples", "p95"}
