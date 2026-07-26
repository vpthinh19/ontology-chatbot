"""Aggregate official multi-seed SPARQL experiment reports."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Iterable


METRICS = (
    "parse_rate",
    "execution_rate",
    "answer_exact_rate",
    "canonical_query_exact_rate",
)


def summarize_experiments(
    root: Path,
    models: Iterable[str] = ("bartpho", "vit5"),
    seeds: Iterable[int] = (7, 21, 42),
) -> dict:
    """Read one validation and benchmark report per model/seed."""

    runs = []
    for model in models:
        for seed in seeds:
            run_dir = root / model / f"seed-{seed}"
            validation = _read_json(run_dir / "metrics.json")
            benchmark = _read_json(run_dir / "benchmark_metrics.json")
            training = validation["training"]
            if training["model"] != model or training["seed"] != seed:
                raise ValueError(f"run metadata does not match path: {run_dir}")
            runs.append(
                {
                    "model": model,
                    "seed": seed,
                    "validation": validation["overall"],
                    "benchmark": benchmark["overall"],
                    "benchmark_by_register": benchmark["by_register"],
                    "benchmark_by_query_shape": benchmark["by_query_shape"],
                    "training": training,
                    "inference": benchmark.get("inference"),
                }
            )

    return {
        "root": str(root),
        "seeds": list(seeds),
        "runs": runs,
        "models": {
            model: _summarize_model([run for run in runs if run["model"] == model])
            for model in models
        },
    }


def _summarize_model(runs: list[dict]) -> dict:
    benchmark_groups = ("benchmark_by_register", "benchmark_by_query_shape")
    result = {
        "run_count": len(runs),
        "validation": _summarize_metric_blocks(run["validation"] for run in runs),
        "benchmark": _summarize_metric_blocks(run["benchmark"] for run in runs),
        "training": {
            "seconds": _summary(run["training"]["train_runtime_seconds"] for run in runs),
            "peak_vram_bytes": _summary(run["training"]["peak_vram_bytes"] for run in runs),
        },
    }
    for group in benchmark_groups:
        names = sorted(set.intersection(*(set(run[group]) for run in runs)))
        result[group.removeprefix("benchmark_")] = {
            name: _summarize_metric_blocks(run[group][name] for run in runs)
            for name in names
        }
    inference = [run["inference"] for run in runs if run["inference"]]
    if inference:
        result["inference"] = {
            "seconds": _summary(item["seconds"] for item in inference),
            "records_per_second": _summary(
                item["records_per_second"] for item in inference
            ),
            "peak_vram_bytes": _summary(item["peak_vram_bytes"] for item in inference),
            "measured_runs": len(inference),
        }
    return result


def _summarize_metric_blocks(blocks: Iterable[dict]) -> dict:
    blocks = list(blocks)
    counts = {block["count"] for block in blocks}
    if len(counts) != 1:
        raise ValueError(f"metric blocks have inconsistent counts: {sorted(counts)}")
    return {
        "count": counts.pop(),
        **{
            metric: _summary(block[metric] for block in blocks)
            for metric in METRICS
        },
    }


def _summary(values: Iterable[float | int]) -> dict[str, float]:
    values = [float(value) for value in values]
    if not values:
        raise ValueError("cannot summarize an empty value collection")
    return {
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"missing experiment report: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("artifacts/sparql_official_v1"),
    )
    parser.add_argument("--models", nargs="+", default=["bartpho", "vit5"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 21, 42])
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = summarize_experiments(args.root, args.models, args.seeds)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
