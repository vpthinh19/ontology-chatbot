"""Metrics computation for multi-label classification."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    hamming_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from transformers import EvalPrediction

# Ordered metric keys for consistent display
METRIC_KEYS = [
    "accuracy",
    "precision",
    "recall",
    "f1_macro",
    "f1_micro",
    "f1_weighted",
    "f1_samples",
    "roc_auc",
    "mAP",
    "hamming_loss",
]


def compute_metrics(
    predictions: np.ndarray,
    labels: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Compute evaluation metrics for multi-label classification.

    Args:
        predictions: Raw logits, shape (N, L).
        labels: Binary ground truth, shape (N, L).
        threshold: Decision threshold on sigmoid probabilities.

    Returns:
        Ordered dict of metric name -> value.
    """
    logits = np.asarray(predictions, dtype=np.float32)
    labels_arr = np.asarray(labels, dtype=np.intp)

    probs = 1.0 / (1.0 + np.exp(-logits))
    y_pred = (probs >= threshold).astype(np.intp, copy=False)

    return {
        "accuracy": float(accuracy_score(labels_arr, y_pred)),
        "precision": float(precision_score(labels_arr, y_pred, average="macro", zero_division=0)),
        "recall": float(recall_score(labels_arr, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(labels_arr, y_pred, average="macro", zero_division=0)),
        "f1_micro": float(f1_score(labels_arr, y_pred, average="micro", zero_division=0)),
        "f1_weighted": float(f1_score(labels_arr, y_pred, average="weighted", zero_division=0)),
        "f1_samples": float(f1_score(labels_arr, y_pred, average="samples", zero_division=0)),
        "roc_auc": float(roc_auc_score(labels_arr, probs, average="macro")),
        "mAP": float(average_precision_score(labels_arr, probs, average="macro")),
        "hamming_loss": float(hamming_loss(labels_arr, y_pred)),
    }


def make_compute_metrics_fn():
    """Create a compute_metrics callback for HuggingFace Trainer."""

    def _fn(p: EvalPrediction) -> dict[str, float]:
        preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
        labels = p.label_ids[0] if isinstance(p.label_ids, tuple) else p.label_ids
        return compute_metrics(np.asarray(preds), np.asarray(labels))

    return _fn
