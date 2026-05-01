"""Tests for ``ontchatbot.viz.training_curves``."""

from __future__ import annotations

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
    assert h["eval_f1"] == [0.5, 0.7]


def test_plot_training_curves_writes_file(tmp_path):
    history = [
        {"loss": 0.9, "epoch": 1.0},
        {"eval_loss": 0.8, "eval_accuracy": 0.7, "eval_f1_macro": 0.6, "epoch": 1.0},
    ]
    out = tmp_path / "curves.png"
    plot_training_curves(history, str(out))
    assert out.is_file() and out.stat().st_size > 0
