"""Pure metrics and threshold calibration for the binary domain gate."""

from __future__ import annotations

import math


def _validate_inputs(labels: list[int], probabilities: list[float]) -> None:
    if not labels or len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must have the same non-zero length")
    if any(label not in (0, 1) for label in labels):
        raise ValueError("labels must be binary")
    if any(not math.isfinite(value) or not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must be finite and between 0 and 1")


def _divide(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _roc_auc(labels: list[int], probabilities: list[float]) -> float:
    positives = [score for label, score in zip(labels, probabilities) if label == 1]
    negatives = [score for label, score in zip(labels, probabilities) if label == 0]
    if not positives or not negatives:
        return 0.0
    wins = sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    )
    return wins / (len(positives) * len(negatives))


def _average_precision(labels: list[int], probabilities: list[float]) -> float:
    positives = sum(labels)
    if not positives:
        return 0.0
    ranked = sorted(
        zip(probabilities, labels, strict=True),
        key=lambda item: item[0],
        reverse=True,
    )
    true_positives = 0
    precision_sum = 0.0
    for rank, (_, label) in enumerate(ranked, start=1):
        if label == 1:
            true_positives += 1
            precision_sum += true_positives / rank
    return precision_sum / positives


def evaluate_gate(
    labels: list[int],
    probabilities: list[float],
    threshold: float,
) -> dict[str, object]:
    """Evaluate acceptance decisions where ``in_scope`` is positive."""

    _validate_inputs(labels, probabilities)
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    predictions = [int(score >= threshold) for score in probabilities]
    tp = sum(label == 1 and prediction == 1 for label, prediction in zip(labels, predictions))
    fn = sum(label == 1 and prediction == 0 for label, prediction in zip(labels, predictions))
    fp = sum(label == 0 and prediction == 1 for label, prediction in zip(labels, predictions))
    tn = sum(label == 0 and prediction == 0 for label, prediction in zip(labels, predictions))
    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    negative_precision = _divide(tn, tn + fn)
    negative_recall = _divide(tn, tn + fp)
    return {
        "threshold": threshold,
        "records": len(labels),
        "confusion": {"tp": tp, "fn": fn, "fp": fp, "tn": tn},
        "accuracy": _divide(tp + tn, len(labels)),
        "in_scope_precision": precision,
        "in_scope_recall": recall,
        "in_scope_f1": _f1(precision, recall),
        "out_of_scope_recall": negative_recall,
        "false_acceptance_rate": _divide(fp, fp + tn),
        "false_rejection_rate": _divide(fn, fn + tp),
        "macro_f1": (_f1(precision, recall) + _f1(negative_precision, negative_recall)) / 2,
        "roc_auc": _roc_auc(labels, probabilities),
        "average_precision": _average_precision(labels, probabilities),
    }


def select_threshold(
    labels: list[int],
    probabilities: list[float],
    *,
    max_false_acceptance: float = 0.01,
) -> float:
    """Maximize in-scope recall under a validation false-acceptance limit."""

    _validate_inputs(labels, probabilities)
    if not 0 <= max_false_acceptance <= 1:
        raise ValueError("max_false_acceptance must be between 0 and 1")
    candidates = sorted(set(probabilities))
    if max(candidates) < 1:
        candidates.append(math.nextafter(max(candidates), math.inf))
    feasible = []
    for threshold in candidates:
        report = evaluate_gate(labels, probabilities, threshold)
        if report["false_acceptance_rate"] <= max_false_acceptance:
            feasible.append((report["in_scope_recall"], -threshold, threshold))
    if not feasible:
        raise ValueError("no threshold satisfies the false-acceptance limit")
    return max(feasible)[2]
