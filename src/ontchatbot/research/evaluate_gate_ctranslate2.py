"""Evaluate the deployed CT2+NumPy gate and compare it with PyTorch output."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .gate_evaluation import evaluate_gate
from ..runtime.gate import CTranslate2DomainGate
from ..settings import GATE_DIR


def evaluate(args: argparse.Namespace) -> dict:
    rows = _load_jsonl(Path(args.dataset_dir) / "test.jsonl")
    baseline = _load_jsonl(Path(args.baseline_predictions))
    if len(rows) != len(baseline):
        raise ValueError("gate test set and baseline predictions have different sizes")
    if any(row["input"] != reference["input"] for row, reference in zip(rows, baseline, strict=True)):
        raise ValueError("gate test set and baseline predictions are not aligned")

    gate = CTranslate2DomainGate.load(
        args.model_dir,
        device=args.device,
        compute_type=args.compute_type,
    )
    started = time.perf_counter()
    decisions = [gate.decide(row["input"]) for row in rows]
    elapsed = time.perf_counter() - started
    labels = [int(row["label"] == "in_scope") for row in rows]
    probabilities = [decision.probability for decision in decisions]
    test_report = evaluate_gate(labels, probabilities, gate.threshold)

    baseline_probabilities = [float(row["in_scope_probability"]) for row in baseline]
    drifts = [
        abs(current - previous)
        for current, previous in zip(probabilities, baseline_probabilities, strict=True)
    ]
    baseline_confusion = _confusion(
        labels,
        [bool(row["accepted"]) for row in baseline],
    )
    decision_differences = sum(
        decision.accepted != bool(reference["accepted"])
        for decision, reference in zip(decisions, baseline, strict=True)
    )
    confusion_matches = test_report["confusion"] == baseline_confusion
    false_acceptance = float(test_report["false_acceptance_rate"])
    in_scope_recall = float(test_report["in_scope_recall"])
    report = {
        "test": test_report,
        "inference": {
            "records": len(rows),
            "device": args.device,
            "compute_type": args.compute_type,
            "seconds": round(elapsed, 3),
            "records_per_second": round(len(rows) / elapsed, 3) if elapsed else 0.0,
        },
        "parity": {
            "baseline": str(args.baseline_predictions),
            "decision_differences": decision_differences,
            "max_probability_drift": round(max(drifts, default=0.0), 12),
            "mean_probability_drift": round(sum(drifts) / len(drifts), 12) if drifts else 0.0,
            "confusion_matrix_matches": confusion_matches,
        },
        "production_criteria": {
            "maximum_false_acceptance_rate": 0.012,
            "minimum_in_scope_recall": 0.95,
            "passed": (
                confusion_matches
                and false_acceptance <= 0.012
                and in_scope_recall >= 0.95
            ),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _confusion(labels: list[int], accepted: list[bool]) -> dict[str, int]:
    return {
        "tp": sum(label == 1 and decision for label, decision in zip(labels, accepted, strict=True)),
        "fn": sum(label == 1 and not decision for label, decision in zip(labels, accepted, strict=True)),
        "fp": sum(label == 0 and decision for label, decision in zip(labels, accepted, strict=True)),
        "tn": sum(label == 0 and not decision for label, decision in zip(labels, accepted, strict=True)),
    }


def _load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--dataset-dir", type=Path, default=GATE_DIR)
    parser.add_argument("--baseline-predictions", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/gate_ct2_metrics.json"),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    evaluate(_parse_args(argv))
