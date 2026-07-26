from __future__ import annotations

import json
from pathlib import Path

import pytest

from ontchatbot.research.reporting import summarize_experiments


def _write_run(root: Path, model: str, seed: int, score: float) -> None:
    run_dir = root / model / f"seed-{seed}"
    run_dir.mkdir(parents=True)
    block = {
        "count": 2,
        "parse_rate": 1.0,
        "execution_rate": 1.0,
        "answer_exact_rate": score,
        "canonical_query_exact_rate": score,
    }
    validation = {
        "overall": block,
        "training": {
            "model": model,
            "seed": seed,
            "train_runtime_seconds": 10 + seed,
            "peak_vram_bytes": 100,
        },
    }
    benchmark = {
        "overall": block,
        "by_register": {"neutral": block},
        "by_query_shape": {"direct": block},
        "inference": {
            "seconds": 2.0,
            "records_per_second": 1.0,
            "peak_vram_bytes": 50,
        },
    }
    (run_dir / "metrics.json").write_text(json.dumps(validation), encoding="utf-8")
    (run_dir / "benchmark_metrics.json").write_text(
        json.dumps(benchmark), encoding="utf-8"
    )


def test_summarizes_runs_with_sample_standard_deviation(tmp_path: Path) -> None:
    _write_run(tmp_path, "vit5", 1, 0.5)
    _write_run(tmp_path, "vit5", 2, 1.0)

    report = summarize_experiments(tmp_path, models=["vit5"], seeds=[1, 2])
    model = report["models"]["vit5"]

    assert model["benchmark"]["answer_exact_rate"]["mean"] == 0.75
    assert model["benchmark"]["answer_exact_rate"]["sample_std"] == pytest.approx(
        0.3535533905932738
    )
    assert model["by_register"]["neutral"]["count"] == 2
    assert model["inference"]["measured_runs"] == 2


def test_rejects_metadata_that_does_not_match_directory(tmp_path: Path) -> None:
    _write_run(tmp_path, "vit5", 1, 1.0)
    path = tmp_path / "vit5/seed-1/metrics.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["training"]["seed"] = 9
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ValueError, match="metadata does not match"):
        summarize_experiments(tmp_path, models=["vit5"], seeds=[1])
