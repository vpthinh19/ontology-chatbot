"""Tests for the ``ontchatbot.viz`` modules — file-creation smoke tests."""

from __future__ import annotations

from ontchatbot.viz.evaluation import (
    plot_classification_report,
    plot_confusion_matrix,
)
from ontchatbot.viz.training_curves import _split_history, plot_training_curves


def test_split_history_separates_streams():
    history = [
        {"loss": 1.2, "epoch": 1.0},
        {"eval_loss": 1.0, "eval_accuracy": 0.6, "eval_f1_macro": 0.5, "epoch": 1.0},
        {"loss": 0.6, "epoch": 2.0},
        {"eval_loss": 0.7, "eval_accuracy": 0.8, "eval_f1_macro": 0.7, "epoch": 2.0},
    ]
    h = _split_history(history)
    assert h["train_loss"] == [1.2, 0.6]
    assert h["eval_loss"] == [1.0, 0.7]
    assert h["eval_acc"] == [0.6, 0.8]
    assert h["eval_f1_macro"] == [0.5, 0.7]


def test_plot_training_curves_writes_file(tmp_path):
    history = [
        {"loss": 0.9, "epoch": 1.0},
        {"eval_loss": 0.8, "eval_accuracy": 0.7, "eval_f1_macro": 0.6, "epoch": 1.0},
    ]
    out = tmp_path / "curves.png"
    plot_training_curves(history, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_confusion_matrix_writes_file(tmp_path):
    labels = ["O", "B-X", "I-X"]
    true = [["B-X", "I-X", "O"], ["B-X", "O", "O"]]
    pred = [["B-X", "I-X", "O"], ["O",   "O", "O"]]
    out = tmp_path / "cm.png"
    plot_confusion_matrix(true, pred, labels, str(out))
    assert out.is_file() and out.stat().st_size > 0


def test_plot_classification_report_writes_file(tmp_path):
    dict_report = {
        "QuyTrinhHocVu":    {"precision": 0.9355, "recall": 0.9355, "f1-score": 0.9355, "support": 93},
        "PhongBanHanhChinh": {"precision": 0.9737, "recall": 1.0000, "f1-score": 0.9867, "support": 74},
        "DinhMucHocPhi":    {"precision": 0.9571, "recall": 0.9437, "f1-score": 0.9504, "support": 71},
        "micro avg":        {"precision": 0.9481, "recall": 0.9705, "f1-score": 0.9592, "support": 847},
        "macro avg":        {"precision": 0.9519, "recall": 0.9671, "f1-score": 0.9594, "support": 847},
        "weighted avg":     {"precision": 0.9481, "recall": 0.9705, "f1-score": 0.9591, "support": 847},
    }
    out = tmp_path / "report.png"
    plot_classification_report(dict_report, accuracy=0.9762, save_path=str(out))
    assert out.is_file() and out.stat().st_size > 0


