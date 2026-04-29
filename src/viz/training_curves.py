"""Training & validation curve visualizations.

Layout: 2x2 grid of subplots (4 panels):
    Train Loss | Val Loss
    Val Acc    | Val F1-Macro
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


# Style registry for known models
MODEL_STYLES: dict[str, dict] = {
    "BCE":   {"color": "#3B82F6", "marker": "o", "linestyle": "-"},
    "ASL":   {"color": "#EF4444", "marker": "D", "linestyle": "-."},
    "ZLPR":  {"color": "#8B5CF6", "marker": "^", "linestyle": ":"},
}

_FALLBACK_COLORS = ["#10B981", "#EC4899", "#06B6D4", "#6366F1"]
_FALLBACK_MARKERS = ["v", "P", "X", "*"]


def _get_style(name: str, idx: int) -> dict:
    """Get line style for a model, fallback to defaults."""
    if name in MODEL_STYLES:
        return MODEL_STYLES[name]
    return {
        "color": _FALLBACK_COLORS[idx % len(_FALLBACK_COLORS)],
        "marker": _FALLBACK_MARKERS[idx % len(_FALLBACK_MARKERS)],
        "linestyle": "-",
    }


def plot_training_curves(
    logs: dict[str, list[dict]],
    save_path: str,
) -> None:
    """Layout: 2x2 grid (4 panels):
        1. Train Loss
        2. Val Loss
        3. Val Accuracy
        4. Val F1-Macro

    Args:
        logs: Mapping of model name to Trainer log_history list.
        save_path: Output image path.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
    axes = axes.flatten()

    for idx, (name, log_history) in enumerate(logs.items()):
        style = _get_style(name, idx)
        common = dict(
            label=name,
            color=style["color"],
            marker=style["marker"],
            linestyle=style["linestyle"],
            markersize=4,
            linewidth=1.5,
            alpha=0.9,
        )

        train_loss, train_epochs = [], []
        eval_loss, eval_epochs = [], []
        eval_f1_macro = []
        eval_acc = []

        for entry in log_history:
            if "loss" in entry and "epoch" in entry:
                train_loss.append(entry["loss"])
                train_epochs.append(entry["epoch"])
            if "eval_loss" in entry and "epoch" in entry:
                eval_loss.append(entry["eval_loss"])
                eval_epochs.append(entry["epoch"])
                eval_f1_macro.append(entry.get("eval_f1_macro", 0))
                eval_acc.append(entry.get("eval_accuracy", 0))

        axes[0].plot(train_epochs, train_loss, **common)
        axes[1].plot(eval_epochs, eval_loss, **common)
        axes[2].plot(eval_epochs, eval_acc, **common)
        axes[3].plot(eval_epochs, eval_f1_macro, **common)

    # Panel configuration: (title, ylabel, is_score)
    panels = [
        ("Train Loss", "Loss", False),
        ("Val Loss", "Loss", False),
        ("Val Accuracy", "Accuracy", True),
        ("Val F1 (Macro)", "F1", True),
    ]

    for ax, (title, ylabel, is_score) in zip(axes, panels):
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.legend(fontsize=9, frameon=True, fancybox=True, loc="best")
        ax.grid(True, alpha=0.15, linestyle="--")
        if is_score:
            ax.set_ylim(-0.02, 1.05)
        sns.despine(ax=ax)

    axes[2].set_xlabel("Epoch", fontsize=11)
    axes[3].set_xlabel("Epoch", fontsize=11)

    fig.suptitle(
        "Training Curves",
        fontsize=16, fontweight="bold", y=1.02,
    )
    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [VIZ] {save_path}")
