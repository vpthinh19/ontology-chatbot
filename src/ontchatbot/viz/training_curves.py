"""Training-curve visualisation for a single NER fine-tuning run.

A 2x2 grid is produced:
    1. train loss     2. validation loss
    3. validation accuracy   4. validation F1 (macro)

The HF ``Trainer.state.log_history`` is consumed directly: train-loss entries
contain ``loss``/``epoch``; eval entries contain ``eval_loss``, ``eval_accuracy``,
``eval_f1_macro`` (and other ``eval_*`` keys produced by ``compute_metrics``).
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


def _split_history(log_history: list[dict]) -> dict[str, list]:
    """Group log entries into train and eval streams."""
    train_loss, train_epochs = [], []
    eval_loss, eval_acc, eval_f1, eval_epochs = [], [], [], []
    for e in log_history:
        if "loss" in e and "epoch" in e and "eval_loss" not in e:
            train_loss.append(e["loss"])
            train_epochs.append(e["epoch"])
        if "eval_loss" in e and "epoch" in e:
            eval_loss.append(e["eval_loss"])
            eval_acc.append(e.get("eval_accuracy", 0.0))
            eval_f1.append(e.get("eval_f1_macro", 0.0))
            eval_epochs.append(e["epoch"])
    return {
        "train_loss": train_loss, "train_epochs": train_epochs,
        "eval_loss": eval_loss, "eval_acc": eval_acc,
        "eval_f1": eval_f1, "eval_epochs": eval_epochs,
    }


def plot_training_curves(log_history: list[dict], save_path: str) -> None:
    h = _split_history(log_history)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    style = dict(color="#3B82F6", marker="o", linewidth=1.5, markersize=4)

    axes[0, 0].plot(h["train_epochs"], h["train_loss"], **style)
    axes[0, 0].set_title("Train Loss", fontweight="bold")
    axes[0, 0].set_ylabel("Loss")

    axes[0, 1].plot(h["eval_epochs"], h["eval_loss"], **style)
    axes[0, 1].set_title("Val Loss", fontweight="bold")
    axes[0, 1].set_ylabel("Loss")

    axes[1, 0].plot(h["eval_epochs"], h["eval_acc"], **style)
    axes[1, 0].set_title("Val Accuracy", fontweight="bold")
    axes[1, 0].set_ylabel("Accuracy")
    axes[1, 0].set_ylim(-0.02, 1.05)
    axes[1, 0].set_xlabel("Epoch")

    axes[1, 1].plot(h["eval_epochs"], h["eval_f1"], **style)
    axes[1, 1].set_title("Val F1 (Macro)", fontweight="bold")
    axes[1, 1].set_ylabel("F1")
    axes[1, 1].set_ylim(-0.02, 1.05)
    axes[1, 1].set_xlabel("Epoch")

    for ax in axes.flat:
        ax.grid(True, alpha=0.2, linestyle="--")
        sns.despine(ax=ax)

    fig.suptitle("PhoBERT NER — Training Curves", fontsize=14, fontweight="bold")
    fig.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
