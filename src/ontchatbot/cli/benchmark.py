"""Validate or score predictions on the canonical SPARQL test set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..research.benchmark import (
    evaluate_benchmark,
    load_benchmark,
    load_predictions,
    load_user_query_expectations,
    reference_predictions,
    validate_benchmark,
)
from ..settings import DATASET_DIR, TEST_DATASET_PATH
from ..research.dataset import load_release
from ..research.evaluation import evaluate_query_id_expectations
from ..runtime.sparql import load_ontology


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=TEST_DATASET_PATH)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument(
        "--real-user-predictions",
        type=Path,
        help="JSONL id=real-user-001..009; chấm riêng, không trộn benchmark",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--details", action="store_true")
    args = parser.parse_args()
    if args.predictions and not args.real_user_predictions:
        parser.error(
            "--predictions requires --real-user-predictions so the separate "
            "9-case report cannot disappear"
        )

    graph = load_ontology()
    rows = load_benchmark(args.benchmark)
    release = load_release(args.dataset_dir)
    validation = validate_benchmark(
        rows,
        graph,
        training_rows=release["train"],
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
    real_user_expectations = load_user_query_expectations()
    if args.real_user_predictions:
        real_user_map = load_predictions(args.real_user_predictions)
        real_user_predictions = [
            real_user_map.get(f"real-user-{index:03d}", "")
            for index in range(1, len(real_user_expectations) + 1)
        ]
        report["real_user_cases"] = evaluate_query_id_expectations(
            real_user_expectations,
            real_user_predictions,
            include_cases=args.details,
        )
        report["real_user_cases"]["prediction_file"] = {
            "missing_ids": [
                f"real-user-{index:03d}"
                for index in range(1, len(real_user_expectations) + 1)
                if f"real-user-{index:03d}" not in real_user_map
            ],
            "unexpected_ids": sorted(
                set(real_user_map)
                - {
                    f"real-user-{index:03d}"
                    for index in range(1, len(real_user_expectations) + 1)
                }
            ),
        }
    else:
        report["real_user_cases"] = {
            "status": "not_scored",
            "count": len(real_user_expectations),
            "reason": "supply --real-user-predictions to score this separate set",
            "mixed_into_generated_benchmark": False,
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
