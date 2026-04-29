"""Unit tests for metrics computation."""

import numpy as np
import pytest

from src.utils.metrics import METRIC_KEYS, compute_metrics, make_compute_metrics_fn


class TestMetricKeys:
    def test_is_list(self):
        assert isinstance(METRIC_KEYS, list)

    def test_expected_keys(self):
        assert "f1_samples" in METRIC_KEYS
        assert "f1_macro" in METRIC_KEYS
        assert "mAP" in METRIC_KEYS
        assert "hamming_loss" in METRIC_KEYS


class TestComputeMetrics:
    def test_output_keys(self):
        logits = np.random.randn(10, 5)
        labels = np.zeros((10, 5))
        # Ensure at least one positive and one negative per class
        for i in range(5):
            labels[i, i] = 1
        result = compute_metrics(logits, labels)
        for key in METRIC_KEYS:
            assert key in result

    def test_output_values_in_range(self):
        logits = np.random.randn(20, 5)
        labels = np.zeros((20, 5))
        for i in range(20):
            labels[i, i % 5] = 1
        result = compute_metrics(logits, labels)

        for key in METRIC_KEYS:
            assert 0 <= result[key] <= 1, f"{key} out of range: {result[key]}"

    def test_perfect_predictions(self):
        """High logits for positive, low for negative → high F1."""
        n_samples, n_labels = 20, 5
        labels = np.zeros((n_samples, n_labels))
        logits = np.full((n_samples, n_labels), -10.0)
        for i in range(n_samples):
            labels[i, i % n_labels] = 1
            logits[i, i % n_labels] = 10.0

        result = compute_metrics(logits, labels)
        assert result["f1_macro"] > 0.9
        assert result["hamming_loss"] < 0.1

    def test_custom_threshold(self):
        logits = np.zeros((6, 3))
        labels = np.zeros((6, 3))
        # Ensure at least one positive and one negative per class
        for i in range(3):
            labels[i, i] = 1
        # With threshold 0.5, sigmoid(0) = 0.5 → exactly at threshold
        result_low = compute_metrics(logits, labels, threshold=0.4)
        result_high = compute_metrics(logits, labels, threshold=0.6)
        # Lower threshold → more predicted positives → higher recall
        assert result_low["recall"] >= result_high["recall"]


class TestMakeComputeMetricsFn:
    def test_returns_callable(self):
        fn = make_compute_metrics_fn()
        assert callable(fn)
