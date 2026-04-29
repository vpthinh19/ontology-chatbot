"""Label distribution visualization."""

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


def _ensure_dir(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)


# Color palette

SPLIT_COLORS = {
    "Train": "#3B82F6",
    "Val": "#10B981",
    "Test": "#F59E0B",
}


def plot_label_distribution(
    splits: dict[str, list[list[str]]],
    label_names: list[str],
    save_path: str,
):
    """Horizontal grouped bar chart of label frequencies per split.

    Each label shows bars for train/val/test with count annotations.
    """
    _ensure_dir(save_path)

    split_counts = {}
    for split_name, labels_list in splits.items():
        counts = {label: 0 for label in label_names}
        for labels in labels_list:
            for label in labels:
                counts[label] = counts.get(label, 0) + 1
        split_counts[split_name] = [counts[label] for label in label_names]

    n_labels = len(label_names)
    n_splits = len(splits)
    y = np.arange(n_labels)
    height = 0.8 / n_splits

    fig, ax = plt.subplots(figsize=(14, max(8, n_labels * 0.6)))

    for i, (split_name, counts) in enumerate(split_counts.items()):
        color = SPLIT_COLORS.get(split_name, plt.cm.tab10(i))
        bars = ax.barh(
            y + i * height, counts, height,
            label=split_name, color=color, edgecolor="white", linewidth=0.5,
        )
        # Annotate counts
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(
                    bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                    str(count), va="center", ha="left", fontsize=7, color="#6B7280",
                )

    ax.set_xlabel("Count", fontsize=11, fontweight="medium")
    ax.set_title("Label Distribution by Split", fontsize=14, fontweight="bold", pad=15)
    ax.set_yticks(y + height * (n_splits - 1) / 2)
    ax.set_yticklabels(label_names, fontsize=9)
    ax.invert_yaxis()
    ax.legend(fontsize=10, frameon=True, fancybox=True, shadow=False, loc="lower right")
    ax.grid(True, axis="x", alpha=0.2, linestyle="--")
    ax.set_axisbelow(True)
    sns.despine(ax=ax, left=True)

    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [VIZ] {save_path}")
