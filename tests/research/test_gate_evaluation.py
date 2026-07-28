from __future__ import annotations

import pytest

from ontchatbot.research.gate_evaluation import evaluate_gate, select_threshold


def test_gate_metrics_use_in_scope_as_positive_class() -> None:
    report = evaluate_gate(
        labels=[1, 1, 1, 0, 0, 0],
        probabilities=[0.95, 0.80, 0.40, 0.70, 0.20, 0.10],
        threshold=0.50,
    )

    assert report["confusion"] == {"tp": 2, "fn": 1, "fp": 1, "tn": 2}
    assert report["in_scope_precision"] == pytest.approx(2 / 3)
    assert report["in_scope_recall"] == pytest.approx(2 / 3)
    assert report["out_of_scope_recall"] == pytest.approx(2 / 3)
    assert report["false_acceptance_rate"] == pytest.approx(1 / 3)
    assert report["false_rejection_rate"] == pytest.approx(1 / 3)
    assert report["accuracy"] == pytest.approx(2 / 3)
    assert report["roc_auc"] == pytest.approx(8 / 9)


def test_threshold_maximizes_recall_within_false_acceptance_limit() -> None:
    labels = [1, 1, 1, 0, 0, 0]
    probabilities = [0.95, 0.80, 0.40, 0.70, 0.20, 0.10]

    threshold = select_threshold(
        labels,
        probabilities,
        max_false_acceptance=0.01,
    )

    assert threshold == pytest.approx(0.80)
    report = evaluate_gate(labels, probabilities, threshold)
    assert report["false_acceptance_rate"] == 0
    assert report["in_scope_recall"] == pytest.approx(2 / 3)


def test_gate_metrics_reject_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="same non-zero length"):
        evaluate_gate([1], [], 0.5)
    with pytest.raises(ValueError, match="binary"):
        evaluate_gate([2], [0.5], 0.5)
    with pytest.raises(ValueError, match="between 0 and 1"):
        evaluate_gate([1], [1.2], 0.5)


def test_threshold_reports_when_false_acceptance_limit_is_impossible() -> None:
    with pytest.raises(ValueError, match="no threshold"):
        select_threshold([1, 0], [0.9, 1.0], max_false_acceptance=0.0)
