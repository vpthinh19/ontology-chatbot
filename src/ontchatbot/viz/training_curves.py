"""Training-curve visualisation for a single NER fine-tuning run.

Renders a 2×3 panel that captures every metric reported by the trainer:

    train loss        | validation loss   | learning rate
    val accuracy      | val F1 (macro)    | val P / R (macro)

The HF ``Trainer.state.log_history`` is consumed directly. Train-loss entries
contain ``loss`` / ``epoch``; eval entries contain ``eval_loss`` plus every
``eval_*`` key produced by ``compute_metrics``.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


def _split_history(history: list[dict]) -> dict[str, list]:
    """Group log entries into train and eval parallel arrays."""
    out: dict[str, list] = {
        "train_loss": [], "train_lr": [], "train_epochs": [],
        "eval_loss": [], "eval_acc": [], "eval_f1_macro": [],
        "eval_precision": [], "eval_recall": [], "eval_f1_micro": [],
        "eval_epochs": [],
    }
    for e in history:
        if "loss" in e and "eval_loss" not in e and "epoch" in e:
            out["train_loss"].append(e["loss"])
            out["train_lr"].append(e.get("learning_rate", 0.0))
            out["train_epochs"].append(e["epoch"])
        if "eval_loss" in e and "epoch" in e:
            out["eval_loss"].append(e["eval_loss"])
            out["eval_acc"].append(e.get("eval_accuracy", 0.0))
            out["eval_f1_macro"].append(e.get("eval_f1_macro", 0.0))
            out["eval_precision"].append(e.get("eval_precision_macro", 0.0))
            out["eval_recall"].append(e.get("eval_recall_macro", 0.0))
            out["eval_f1_micro"].append(e.get("eval_f1_micro", 0.0))
            out["eval_epochs"].append(e["epoch"])
    return out


def _line(ax, x, y, *, color, title, ylabel, score=False):
    ax.plot(x, y, color=color, marker="o", linewidth=1.5, markersize=4)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Epoch")
    ax.grid(True, alpha=0.2, linestyle="--")
    if score:
        ax.set_ylim(-0.02, 1.05)
    sns.despine(ax=ax)


def plot_training_curves(history: list[dict], save_path: str) -> None:
    h = _split_history(history)

    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    _line(axes[0, 0], h["train_epochs"], h["train_loss"],
          color="#3B82F6", title="Train Loss", ylabel="Loss")
    _line(axes[0, 1], h["eval_epochs"], h["eval_loss"],
          color="#EF4444", title="Val Loss", ylabel="Loss")
    _line(axes[0, 2], h["train_epochs"], h["train_lr"],
          color="#F59E0B", title="Learning Rate", ylabel="LR")
    _line(axes[1, 0], h["eval_epochs"], h["eval_acc"],
          color="#10B981", title="Val Accuracy", ylabel="Acc", score=True)
    _line(axes[1, 1], h["eval_epochs"], h["eval_f1_macro"],
          color="#8B5CF6", title="Val F1 (Macro)", ylabel="F1", score=True)

    ax = axes[1, 2]
    ax.plot(h["eval_epochs"], h["eval_precision"], color="#06B6D4",
            marker="o", linewidth=1.5, markersize=4, label="Precision (macro)")
    ax.plot(h["eval_epochs"], h["eval_recall"], color="#EC4899",
            marker="s", linewidth=1.5, markersize=4, label="Recall (macro)")
    ax.plot(h["eval_epochs"], h["eval_f1_micro"], color="#6366F1",
            marker="^", linewidth=1.5, markersize=4, label="F1 (micro)")
    ax.set_title("Val Precision / Recall / F1-micro", fontsize=12, fontweight="bold")
    ax.set_ylabel("Score")
    ax.set_xlabel("Epoch")
    ax.set_ylim(-0.02, 1.05)
    ax.grid(True, alpha=0.2, linestyle="--")
    ax.legend(fontsize=9, loc="lower right", frameon=True)
    sns.despine(ax=ax)

    fig.suptitle("PhoBERT NER — Training Diagnostics",
                 fontsize=15, fontweight="bold")
    fig.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
