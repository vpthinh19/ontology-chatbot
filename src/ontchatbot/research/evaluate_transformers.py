"""Evaluate a saved BARTpho or ViT5 checkpoint without retraining it."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .benchmark import evaluate_benchmark, load_benchmark, validate_benchmark
from .dataset import load_release, validate_release
from .evaluation import evaluate_predictions
from ..runtime.text import normalize_model_input
from ..runtime.sparql import load_ontology
from .training import MAX_SOURCE_LENGTH, MAX_TARGET_LENGTH


def evaluate(args: argparse.Namespace) -> dict:
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - CLI requires train extra.
        raise RuntimeError("install the train extra to evaluate models") from exc

    graph = load_ontology()
    release = load_release()
    validate_release(release, graph)
    training_rows = release["train"] + release["val"]
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_dir,
        local_files_only=True,
        trust_remote_code=args.model == "bartpho",
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        args.model_dir,
        local_files_only=True,
        dtype=torch.bfloat16,
        attn_implementation="sdpa" if args.model == "bartpho" else "eager",
    ).to("cuda")
    model.eval()

    output_dir = args.output_dir or args.model_dir.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    if args.suite in {"validation", "both"}:
        rows = release["val"]
        predictions, inference = _generate(model, tokenizer, rows, torch, args.batch_size)
        report = evaluate_predictions(rows, predictions, graph, include_cases=True)
        report["inference"] = inference
        _write_report(output_dir / "validation_metrics.json", report)
        _write_predictions(output_dir / "validation_predictions.jsonl", rows, predictions)
        reports["validation"] = report["overall"]

    if args.suite in {"benchmark", "both"}:
        rows = load_benchmark()
        benchmark_validation = validate_benchmark(
            rows,
            graph,
            training_rows=training_rows,
        )
        predictions, inference = _generate(model, tokenizer, rows, torch, args.batch_size)
        prediction_map = dict(
            zip((row["id"] for row in rows), predictions, strict=True)
        )
        report = evaluate_benchmark(
            rows,
            prediction_map,
            graph,
            include_cases=True,
        )
        report["benchmark"] = benchmark_validation
        report["inference"] = inference
        _write_report(output_dir / "benchmark_metrics.json", report)
        _write_predictions(output_dir / "benchmark_predictions.jsonl", rows, predictions)
        reports["benchmark"] = report["overall"]

    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return reports


def _generate(model, tokenizer, rows, torch, batch_size: int):
    predictions = []
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            encoded = tokenizer(
                [normalize_model_input(row["input"]) for row in batch],
                max_length=MAX_SOURCE_LENGTH,
                truncation=True,
                padding=True,
                pad_to_multiple_of=8,
                return_tensors="pt",
            ).to(model.device)
            output = model.generate(
                **encoded,
                max_length=MAX_TARGET_LENGTH,
                num_beams=1,
            )
            predictions.extend(
                text.strip()
                for text in tokenizer.batch_decode(
                    output,
                    skip_special_tokens=True,
                )
            )
    elapsed = time.perf_counter() - start
    return predictions, {
        "records": len(rows),
        "batch_size": batch_size,
        "seconds": round(elapsed, 3),
        "records_per_second": round(len(rows) / elapsed, 3),
        "peak_vram_bytes": (
            torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None
        ),
    }


def _write_report(path: Path, report: dict) -> None:
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_predictions(path: Path, rows, predictions) -> None:
    path.write_text(
        "".join(
            json.dumps(
                {"id": row["id"], "prediction": prediction},
                ensure_ascii=False,
            )
            + "\n"
            for row, prediction in zip(rows, predictions, strict=True)
        ),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("bartpho", "vit5"), required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--suite", choices=("validation", "benchmark", "both"), default="both")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if not args.model_dir.is_dir():
        parser.error(f"model directory does not exist: {args.model_dir}")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    return args


def main() -> None:
    evaluate(_parse_args())


if __name__ == "__main__":
    main()
