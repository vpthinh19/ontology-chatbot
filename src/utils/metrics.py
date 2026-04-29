"""Metrics computation for multi-label classification (legacy) and multi-class classification.

This project originally implemented multi-label classification metrics (sigmoid + threshold)
using binary ground truth vectors.

After converting the dataset to multiclass (single label per sample), we extend this
module to also support multiclass metrics while keeping the existing multilabel API
and METRIC_KEYS unchanged, so current tests and code paths continue to work.
"""

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
    """Compute evaluation metrics.

    Supports two modes depending on label shape:

    - Multilabel:
        logits: (N, L)
        labels: (N, L) in {0,1}
        Uses sigmoid + threshold to obtain predictions.

    - Multiclass:
        logits: (N, C)
        labels: (N,) in integer class ids
        Uses softmax + argmax to obtain predictions.

    Args:
        predictions: Raw model outputs (logits).
        labels: Ground truth labels (binary matrix for multilabel, class ids for multiclass).
        threshold: Decision threshold used for multilabel mode.

    Returns:
        dict of metric name -> value.
    """
    logits = np.asarray(predictions, dtype=np.float32)
    labels_arr = np.asarray(labels)

    # -----------------------------
    # Multiclass branch
    # -----------------------------
    if labels_arr.ndim == 1:
        y_true = labels_arr.astype(np.int64, copy=False)
        n_samples = y_true.shape[0]
        if logits.ndim != 2:
            raise ValueError(f"Multiclass expects logits.ndim==2, got {logits.ndim}")
        probs = _softmax(logits, axis=-1)
        y_pred = np.argmax(probs, axis=-1)

        precision = precision_score(y_true, y_pred, average="macro", zero_division=0)
        recall = recall_score(y_true, y_pred, average="macro", zero_division=0)
        f1_macro = f1_score(y_true, y_pred, average="macro", zero_division=0)
        f1_micro = f1_score(y_true, y_pred, average="micro", zero_division=0)
        f1_weighted = f1_score(y_true, y_pred, average="weighted", zero_division=0)

        # f1_samples isn't defined for single-label multiclass; keep a deterministic proxy.
        f1_samples = f1_micro

        # ROC-AUC and mAP: do one-vs-rest using class probabilities.
        n_classes = probs.shape[1]
        y_true_bin = np.eye(n_classes, dtype=np.intp)[y_true]

        try:
            roc_auc = roc_auc_score(y_true_bin, probs, average="macro", multi_class="ovr")
        except Exception:
            roc_auc = 0.0

        try:
            mAP = average_precision_score(y_true_bin, probs, average="macro")
        except Exception:
            mAP = 0.0

        # For multiclass, approximate hamming_loss as "misclassification rate".
        # (hamming_loss for multilabel is mean of per-label mismatches).
        h_loss = 1.0 - float(accuracy_score(y_true, y_pred))

        return {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision": float(precision),
            "recall": float(recall),
            "f1_macro": float(f1_macro),
            "f1_micro": float(f1_micro),
            "f1_weighted": float(f1_weighted),
            "f1_samples": float(f1_samples),
            "roc_auc": float(roc_auc),
            "mAP": float(mAP),
            "hamming_loss": float(h_loss),
        }

    # -----------------------------
    # Multilabel branch (legacy)
    # -----------------------------
    logits = np.asarray(predictions, dtype=np.float32)
    labels_bin = np.asarray(labels, dtype=np.intp)
    if labels_bin.ndim != 2:
        raise ValueError(f"Multilabel expects labels.ndim==2, got {labels_bin.ndim}")

    probs = _sigmoid(logits)
    y_pred = (probs >= threshold).astype(np.intp, copy=False)

    return {
        "accuracy": float(accuracy_score(labels_bin, y_pred)),
        "precision": float(
            precision_score(labels_bin, y_pred, average="macro", zero_division=0)
        ),
        "recall": float(
            recall_score(labels_bin, y_pred, average="macro", zero_division=0)
        ),
        "f1_macro": float(f1_score(labels_bin, y_pred, average="macro", zero_division=0)),
        "f1_micro": float(f1_score(labels_bin, y_pred, average="micro", zero_division=0)),
        "f1_weighted": float(
            f1_score(labels_bin, y_pred, average="weighted", zero_division=0)
        ),
        "f1_samples": float(f1_score(labels_bin, y_pred, average="samples", zero_division=0)),
        "roc_auc": float(roc_auc_score(labels_bin, probs, average="macro")),
        "mAP": float(average_precision_score(labels_bin, probs, average="macro")),
        "hamming_loss": float(hamming_loss(labels_bin, y_pred)),
    }


def make_compute_metrics_fn():
    """Create a compute_metrics callback for HuggingFace Trainer."""

    def _fn(p: EvalPrediction) -> dict[str, float]:
        preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
        labels = p.label_ids[0] if isinstance(p.label_ids, tuple) else p.label_ids
        return compute_metrics(np.asarray(preds), np.asarray(labels))

    return _fn
