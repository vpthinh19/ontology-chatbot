"""Tests for the ``ontchatbot.viz`` modules — file-creation smoke tests."""

from __future__ import annotations

from ontchatbot.viz.distributions import (
    plot_label_distribution,
    plot_length_distribution,
)
from ontchatbot.viz.evaluation import (
    plot_confusion_matrix,
    plot_per_class_metrics,
    plot_summary_table,
)
from ontchatbot.viz.training_curves import _split_history, plot_training_curves


def test_split_history_separates_streams():
    history = [
        {"loss": 1.2, "learning_rate": 5e-5, "epoch": 1.0},
        {"eval_loss": 1.0, "eval_accuracy": 0.6, "eval_f1_macro": 0.5,
         "eval_precision_macro": 0.55, "eval_recall_macro": 0.5,
         "eval_f1_micro": 0.7, "epoch": 1.0},
        {"loss": 0.6, "learning_rate": 4e-5, "epoch": 2.0},
        {"eval_loss": 0.7, "eval_accuracy": 0.8, "eval_f1_macro": 0.7,
         "eval_precision_macro": 0.75, "eval_recall_macro": 0.7,
         "eval_f1_micro": 0.85, "epoch": 2.0},
    ]
    h = _split_history(history)
    assert h["train_loss"] == [1.2, 0.6]
    assert h["eval_loss"] == [1.0, 0.7]
    assert h["eval_acc"] == [0.6, 0.8]
    assert h["eval_f1_macro"] == [0.5, 0.7]
    assert h["eval_precision"] == [0.55, 0.75]


def test_plot_training_curves_writes_file(tmp_path):
    history = [
        {"loss": 0.9, "learning_rate": 5e-5, "epoch": 1.0},
        {"eval_loss": 0.8, "eval_accuracy": 0.7, "eval_f1_macro": 0.6,
         "eval_precision_macro": 0.6, "eval_recall_macro": 0.55,
         "eval_f1_micro": 0.7, "epoch": 1.0},
    ]
    out = tmp_path / "curves.png"
    plot_training_curves(history, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_per_class_metrics_writes_file(tmp_path):
    report = {
        "QuyTrinhHocVu": {"precision": 0.9, "recall": 0.8, "f1-score": 0.85, "support": 30},
        "PhongBanHanhChinh": {"precision": 0.7, "recall": 0.9, "f1-score": 0.79, "support": 20},
        "macro avg": {"precision": 0.8, "recall": 0.85, "f1-score": 0.82, "support": 50},
    }
    out = tmp_path / "per_class.png"
    plot_per_class_metrics(report, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_confusion_matrix_writes_file(tmp_path):
    labels = ["O", "B-X", "I-X"]
    true = [["B-X", "I-X", "O"], ["B-X", "O", "O"]]
    pred = [["B-X", "I-X", "O"], ["O",   "O", "O"]]
    out = tmp_path / "cm.png"
    plot_confusion_matrix(true, pred, labels, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_summary_table_writes_file(tmp_path):
    metrics = {
        "n_test": 42, "token_accuracy": 0.95,
        "precision_macro": 0.88, "recall_macro": 0.84, "f1_macro": 0.86,
        "precision_micro": 0.90, "recall_micro": 0.88, "f1_micro": 0.89,
    }
    out = tmp_path / "summary.png"
    plot_summary_table(metrics, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_label_distribution_writes_file(tmp_path):
    splits = {
        "train": [
            {"tokens": ["a", "b"], "ner_tags": ["B-QuyTrinhHocVu", "O"]},
            {"tokens": ["c"], "ner_tags": ["O"]},
        ],
        "test": [
            {"tokens": ["d", "e"], "ner_tags": ["B-PhongBanHanhChinh", "I-PhongBanHanhChinh"]},
        ],
    }
    out = tmp_path / "dist.png"
    plot_label_distribution(splits, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_length_distribution_writes_file(tmp_path):
    splits = {
        "train": [{"tokens": ["a", "b", "c"], "ner_tags": ["O", "O", "O"]}],
        "test": [{"tokens": ["x"], "ner_tags": ["O"]}],
    }
    out = tmp_path / "lengths.png"
    plot_length_distribution(splits, str(out), max_length=128)
    assert out.is_file() and out.stat().st_size > 0
