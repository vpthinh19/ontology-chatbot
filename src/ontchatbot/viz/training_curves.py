"""Training-curve visualisation for a single NER fine-tuning run.

Renders a 2×2 panel — the canonical four diagnostics for token classification:

    train loss      | validation loss
    val accuracy    | val F1 (macro)

The HF ``Trainer.state.log_history`` is consumed directly. Train-loss entries
contain ``loss`` / ``epoch``; eval entries contain ``eval_loss`` plus every
``eval_*`` key produced by ``compute_metrics`` — only the four needed here
are read so the plotter is forward-compatible with extra metrics.
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
        "train_loss": [], "train_epochs": [],
        "eval_loss": [], "eval_acc": [], "eval_f1_macro": [],
        "eval_epochs": [],
    }
    for e in history:
        if "loss" in e and "eval_loss" not in e and "epoch" in e:
            out["train_loss"].append(e["loss"])
            out["train_epochs"].append(e["epoch"])
        if "eval_loss" in e and "epoch" in e:
            out["eval_loss"].append(e["eval_loss"])
            out["eval_acc"].append(e.get("eval_accuracy", 0.0))
            out["eval_f1_macro"].append(e.get("eval_f1_macro", 0.0))
            out["eval_epochs"].append(e["epoch"])
    return out


def _line(ax, x, y, *, color, title, ylabel, score: bool = False) -> None:
    ax.plot(x, y, color=color, marker="o", linewidth=1.6, markersize=4)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Epoch")
    ax.grid(True, alpha=0.2, linestyle="--")
    if score:
        ax.set_ylim(-0.02, 1.05)
    sns.despine(ax=ax)


def plot_training_curves(history: list[dict], save_path: str) -> None:
    h = _split_history(history)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    _line(axes[0, 0], h["train_epochs"], h["train_loss"],
          color="#3B82F6", title="Train Loss", ylabel="Loss")
    _line(axes[0, 1], h["eval_epochs"], h["eval_loss"],
          color="#EF4444", title="Val Loss", ylabel="Loss")
    _line(axes[1, 0], h["eval_epochs"], h["eval_acc"],
          color="#10B981", title="Val Accuracy", ylabel="Accuracy", score=True)
    _line(axes[1, 1], h["eval_epochs"], h["eval_f1_macro"],
          color="#8B5CF6", title="Val F1 (Macro)", ylabel="F1", score=True)

    fig.suptitle("PhoBERT NER — Training Diagnostics",
                 fontsize=15, fontweight="bold")
    fig.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
