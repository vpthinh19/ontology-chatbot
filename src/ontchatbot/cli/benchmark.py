"""Validate or score predictions on the frozen direct-SPARQL benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..research.benchmark import (
    evaluate_benchmark,
    load_benchmark,
    load_predictions,
    reference_predictions,
    validate_benchmark,
)
from ..settings import DATASET_DIR, TEST_DATASET_PATH
from ..research.dataset import load_release
from ..runtime.sparql import load_ontology


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=TEST_DATASET_PATH)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()

    graph = load_ontology()
    rows = load_benchmark(args.benchmark)
    release = load_release(args.dataset_dir)
    validation = validate_benchmark(
        rows,
        graph,
        training_rows=release["train"] + release["val"],
    )
    predictions = (
        load_predictions(args.predictions)
        if args.predictions
        else reference_predictions(rows)
    )
    report = evaluate_benchmark(
        rows,
        predictions,
        graph,
        include_cases=args.details,
    )
    report["benchmark"] = validation
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
