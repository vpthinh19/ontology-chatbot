"""Tokenizer and validation-learning evidence for dataset audits."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from ..runtime.text import normalize_model_input
from .dataset import REQUIRED_SPLITS

MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 160


def tokenizer_report(
    name: str,
    tokenizer: Any,
    release: Mapping[str, list[dict[str, str]]],
) -> dict[str, Any]:
    rows = [row for split in REQUIRED_SPLITS for row in release[split]]
    source_lengths = []
    source_unknown_records = []
    for row in rows:
        ids = tokenizer(
            normalize_model_input(row["input"]),
            add_special_tokens=True,
        )["input_ids"]
        source_lengths.append(len(ids))
        if tokenizer.unk_token_id is not None and tokenizer.unk_token_id in ids:
            source_unknown_records.append(row["id"])

    unique_targets = sorted({row["target"] for row in rows})
    target_lengths = []
    target_unknown_tokens = 0
    target_roundtrip_failures = 0
    target_over_budget = 0
    for target in unique_targets:
        ids = tokenizer(target, add_special_tokens=True)["input_ids"]
        target_lengths.append(len(ids))
        target_unknown_tokens += (
            ids.count(tokenizer.unk_token_id) if tokenizer.unk_token_id is not None else 0
        )
        if len(ids) > MAX_TARGET_LENGTH:
            target_over_budget += 1
        decoded = tokenizer.decode(ids, skip_special_tokens=True).strip()
        target_roundtrip_failures += decoded != target

    return {
        "name": name,
        "vocab_size": len(tokenizer),
        "source_tokens": _summary(source_lengths),
        "target_tokens": _summary(target_lengths),
        "source_over_budget_records": sum(length > MAX_SOURCE_LENGTH for length in source_lengths),
        "source_unknown_records": source_unknown_records,
        "target_over_budget_targets": target_over_budget,
        "target_unknown_tokens": target_unknown_tokens,
        "target_roundtrip_failures": target_roundtrip_failures,
    }

def learning_evidence_report(
    release: Mapping[str, list[dict[str, str]]],
    reports: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not reports:
        return {"available": False, "runs": 0}

    val_by_id = {row["id"]: row for row in release["val"]}
    train_targets = {row["target"] for row in release["train"]}
    run_rows = []
    observations_by_model: dict[str, Counter[str]] = defaultdict(Counter)
    model_register_observations: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    model_shape_observations: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    model_family_observations: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    model_target_observations: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    record_observations: dict[str, Counter[str]] = defaultdict(Counter)
    family_observations: dict[str, Counter[str]] = defaultdict(Counter)
    target_observations: dict[str, Counter[str]] = defaultdict(Counter)
    register_observations: dict[str, Counter[str]] = defaultdict(Counter)
    shape_observations: dict[str, Counter[str]] = defaultdict(Counter)
    novelty_observations: dict[str, Counter[str]] = defaultdict(Counter)
    model_novelty_observations: dict[str, dict[str, Counter[str]]] = defaultdict(
        lambda: defaultdict(Counter)
    )
    error_counts: Counter[str] = Counter()

    for report in reports:
        training = report.get("training", {})
        model = str(training.get("model", "unknown"))
        seed = training.get("seed")
        cases = report["cases"]
        unknown_ids = sorted({case["id"] for case in cases} - val_by_id.keys())
        if unknown_ids:
            raise ValueError(f"validation report contains unknown IDs: {unknown_ids[:5]}")
        exact_count = 0
        for case in cases:
            row = val_by_id[case["id"]]
            exact = bool(case["answer_exact"])
            novelty = (
                "seen_exact_target"
                if row["target"] in train_targets
                else "unseen_exact_target_seen_terms"
            )
            exact_count += exact
            for counter in (
                observations_by_model[model],
                record_observations[row["id"]],
                family_observations[row["family_id"]],
                target_observations[row["target"]],
                register_observations[row["register"]],
                shape_observations[row["query_shape"]],
                model_register_observations[model][row["register"]],
                model_shape_observations[model][row["query_shape"]],
                model_family_observations[model][row["family_id"]],
                model_target_observations[model][row["target"]],
                novelty_observations[novelty],
                model_novelty_observations[model][novelty],
            ):
                counter["observations"] += 1
                counter["exact"] += exact
            if not exact:
                error_counts[str(case.get("error_category") or "unknown")] += 1
        run_rows.append(
            {
                "model": model,
                "seed": seed,
                "records": len(cases),
                "answer_exact_rate": exact_count / len(cases) if cases else 0.0,
                "path": report.get("_audit_path"),
                "sha256": report.get("_audit_sha256"),
            }
        )

    model_runs = Counter(row["model"] for row in run_rows)
    train_target_records = Counter(row["target"] for row in release["train"])
    train_target_families: dict[str, set[str]] = defaultdict(set)
    for row in release["train"]:
        train_target_families[row["target"]].add(row["family_id"])

    target_difficulty = []
    for target, counts in target_observations.items():
        target_difficulty.append(
            {
                "target": target,
                "validation_observations": counts["observations"],
                "answer_exact_rate": _rate(counts),
                "train_records": train_target_records[target],
                "train_families": len(train_target_families[target]),
                "by_model": {
                    model: _rate(model_target_observations[model][target])
                    for model in sorted(observations_by_model)
                },
            }
        )
    target_difficulty.sort(key=lambda row: (row["answer_exact_rate"], row["target"]))

    family_difficulty = [
        {
            "family_id": family,
            "observations": counts["observations"],
            "answer_exact_rate": _rate(counts),
            "by_model": {
                model: _rate(model_family_observations[model][family])
                for model in sorted(observations_by_model)
            },
        }
        for family, counts in family_observations.items()
    ]
    family_difficulty.sort(key=lambda row: (row["answer_exact_rate"], row["family_id"]))
    persistently_failed = sorted(
        record_id
        for record_id, counts in record_observations.items()
        if counts["exact"] == 0
    )
    return {
        "available": True,
        "runs": len(run_rows),
        "run_details": sorted(run_rows, key=lambda row: (row["model"], row["seed"])),
        "by_model": {
            model: {
                "runs": model_runs[model],
                "observations": counts["observations"],
                "answer_exact_rate": _rate(counts),
                "by_register": _rated_counters(model_register_observations[model]),
                "by_query_shape": _rated_counters(model_shape_observations[model]),
                "by_target_novelty": _rated_counters(model_novelty_observations[model]),
            }
            for model, counts in sorted(observations_by_model.items())
        },
        "by_register": _rated_counters(register_observations),
        "by_query_shape": _rated_counters(shape_observations),
        "by_target_novelty": _rated_counters(novelty_observations),
        "error_counts": dict(sorted(error_counts.items())),
        "persistently_failed_records": persistently_failed,
        "persistently_failed_by_register": dict(
            sorted(Counter(val_by_id[record_id]["register"] for record_id in persistently_failed).items())
        ),
        "persistently_failed_by_query_shape": dict(
            sorted(
                Counter(val_by_id[record_id]["query_shape"] for record_id in persistently_failed).items()
            )
        ),
        "hard_families": [row for row in family_difficulty if row["answer_exact_rate"] <= 0.5],
        "family_difficulty": family_difficulty,
        "target_difficulty": target_difficulty,
    }

def _summary(values: Sequence[int]) -> dict[str, int | float]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "min": 0, "p50": 0, "p95": 0, "max": 0, "mean": 0.0}
    return {
        "count": len(ordered),
        "min": ordered[0],
        "p50": _percentile(ordered, 0.50),
        "p95": _percentile(ordered, 0.95),
        "max": ordered[-1],
        "mean": round(sum(ordered) / len(ordered), 6),
    }


def _percentile(values: Sequence[int], quantile: float) -> int:
    index = max(0, math.ceil(len(values) * quantile) - 1)
    return values[index]


def _rate(counter: Counter[str]) -> float:
    return counter["exact"] / counter["observations"] if counter["observations"] else 0.0


def _rated_counters(counters: Mapping[str, Counter[str]]) -> dict[str, dict[str, Any]]:
    return {
        name: {
            "observations": counts["observations"],
            "answer_exact_rate": _rate(counts),
        }
        for name, counts in sorted(counters.items())
    }
