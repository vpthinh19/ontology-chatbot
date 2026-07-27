"""Evaluate a converted CTranslate2 model on the canonical test set."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .benchmark import evaluate_benchmark, load_benchmark, validate_benchmark
from .dataset import load_release
from ..runtime.model import CTranslate2Generator
from ..runtime.sparql import load_ontology


def evaluate(args: argparse.Namespace) -> dict:
    graph = load_ontology()
    rows = load_benchmark()
    release = load_release()
    validation = validate_benchmark(
        rows,
        graph,
        training_rows=release["train"],
    )
    generator = CTranslate2Generator.load(
        args.model_dir,
        device=args.device,
        compute_type=args.compute_type,
    )
    started = time.perf_counter()
    predictions = {row["id"]: generator.generate(row["input"]) for row in rows}
    elapsed = time.perf_counter() - started
    report = evaluate_benchmark(rows, predictions, graph, include_cases=True)
    report["benchmark"] = validation
    report["inference"] = {
        "records": len(rows),
        "device": args.device,
        "compute_type": args.compute_type,
        "seconds": round(elapsed, 3),
        "records_per_second": round(len(rows) / elapsed, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"overall": report["overall"], "inference": report["inference"]}, indent=2))
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/ct2_benchmark_metrics.json"),
    )
    return parser.parse_args()


def main() -> None:
    evaluate(_parse_args())


if __name__ == "__main__":
    main()
