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


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    x = x - np.max(x, axis=axis, keepdims=True)
    exp = np.exp(x)
    return exp / np.sum(exp, axis=axis, keepdims=True)


def compute_metrics(
    predictions: np.ndarray,
    labels: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Compute multilabel evaluation metrics."""
    logits = np.asarray(predictions, dtype=np.float32)
    labels_bin = np.asarray(labels, dtype=np.intp)
    if labels_bin.ndim != 2:
        raise ValueError(f"Multilabel expects labels.ndim==2, got {labels_bin.ndim}")

    probs = _sigmoid(logits)
    y_pred = (probs >= threshold).astype(np.intp, copy=False)

    roc_auc = 0.0
    mAP = 0.0
    try:
        roc_auc = float(roc_auc_score(labels_bin, probs, average="macro"))
    except Exception:
        roc_auc = 0.0
    try:
        mAP = float(average_precision_score(labels_bin, probs, average="macro"))
    except Exception:
        mAP = 0.0

    return {
        "accuracy": float(accuracy_score(labels_bin, y_pred)),
        "precision": float(precision_score(labels_bin, y_pred, average="macro", zero_division=0)),
        "recall": float(recall_score(labels_bin, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(labels_bin, y_pred, average="macro", zero_division=0)),
        "f1_micro": float(f1_score(labels_bin, y_pred, average="micro", zero_division=0)),
        "f1_weighted": float(f1_score(labels_bin, y_pred, average="weighted", zero_division=0)),
        "f1_samples": float(f1_score(labels_bin, y_pred, average="samples", zero_division=0)),
        "roc_auc": roc_auc,
        "mAP": mAP,
        "hamming_loss": float(hamming_loss(labels_bin, y_pred)),
    }


def make_compute_metrics_fn():
    """Create a compute_metrics callback for HuggingFace Trainer."""

    def _fn(p: EvalPrediction) -> dict[str, float]:
        preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
        labels = p.label_ids[0] if isinstance(p.label_ids, tuple) else p.label_ids
        return compute_metrics(np.asarray(preds), np.asarray(labels))

    return _fn
