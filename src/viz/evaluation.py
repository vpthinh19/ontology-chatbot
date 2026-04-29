"""Evaluation visualizations: benchmark comparison, co-occurrence, summary table."""

from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


# Color palette for known models
MODEL_COLORS: dict[str, str] = {
    "BCE": "#3B82F6",
    "Focal": "#F59E0B",
    "ASL": "#EF4444",
    "ZLPR": "#8B5CF6",
}

_FALLBACK_COLORS = ["#10B981", "#EC4899", "#06B6D4"]


def _get_color(name: str, idx: int) -> str:
    return MODEL_COLORS.get(name, _FALLBACK_COLORS[idx % len(_FALLBACK_COLORS)])


# Benchmark comparison — 3 subplots (1 top spanning 2 cols, 2 bottom)

def plot_metrics_comparison(
    metrics: dict[str, dict[str, float]],
    save_path: str,
    title: str = "Benchmark Results",
) -> None:
    """Grouped bar chart comparing metrics across models in a 3-subplot layout.

    Args:
        metrics: {model_name: {metric_name: value}}.
        save_path: Output image path.
        title: Figure suptitle.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    model_names = list(metrics.keys())
    n_models = len(model_names)

    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(2, 2)
    
    # Panels: (subplot, title, metric_keys, lower_is_better)
    panels = [
        (fig.add_subplot(gs[0, :]), "Primary Metrics", ["accuracy", "precision", "recall", "f1_macro"], False),
        (fig.add_subplot(gs[1, 0]), "Ranking", ["mAP", "roc_auc"], False),
        (fig.add_subplot(gs[1, 1]), "Error", ["hamming_loss"], True),
    ]

    for ax, panel_title, metric_keys, lower_better in panels:
        n_metrics = len(metric_keys)
        x = np.arange(n_metrics)
        width = 0.8 / n_models

        for i, name in enumerate(model_names):
            vals = [metrics[name].get(k, 0) for k in metric_keys]
            color = _get_color(name, i)
            bars = ax.bar(
                x + i * width, vals, width,
                label=name, color=color, edgecolor="white", linewidth=0.5,
            )
            # Value annotations
            for bar, val in zip(bars, vals):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + (0.005 if not lower_better else max(vals)*0.01),
                    f"{val:.4f}",
                    ha="center", va="bottom", fontsize=8, color="#4B5563",
                )

        ax.set_xticks(x + width * (n_models - 1) / 2)
        
        # Rename f1_macro to f1 (macro) for display
        display_keys = ["f1 (macro)" if k == "f1_macro" else k for k in metric_keys]
        ax.set_xticklabels(display_keys, fontsize=10)
        
        ax.set_title(panel_title, fontsize=13, fontweight="bold", pad=10)
        ax.set_ylabel("Score", fontsize=11)
        ax.legend(fontsize=9, frameon=True, fancybox=True, loc="best")
        ax.grid(True, axis="y", alpha=0.15, linestyle="--")
        ax.set_axisbelow(True)

        if lower_better:
            ax.set_ylabel("Hamming Loss (lower = better)", fontsize=11)
        else:
            ax.set_ylim(0, 1.12)

        sns.despine(ax=ax)

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [VIZ] {save_path}")


# Summary table

def plot_summary_table(
    metrics: dict[str, dict[str, float]],
    save_path: str,
    title: str = "Summary Table",
) -> None:
    """Render a formatted metrics table as an image.

    Args:
        metrics: {model_name: {metric_name: value}}.
        save_path: Output image path.
        title: Figure title.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    from ..utils.metrics import METRIC_KEYS

    model_names = list(metrics.keys())
    cell_text = []
    for name in model_names:
        row = [f"{metrics[name].get(k, 0):.4f}" for k in METRIC_KEYS]
        cell_text.append(row)

    fig, ax = plt.subplots(figsize=(16, 1.5 + 0.5 * len(model_names)))
    ax.axis("off")

    table = ax.table(
        cellText=cell_text,
        rowLabels=model_names,
        colLabels=METRIC_KEYS,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.8)

    # Style header row
    for j in range(len(METRIC_KEYS)):
        cell = table[0, j]
        cell.set_facecolor("#E5E7EB")
        cell.set_text_props(fontweight="bold")

    # Style row labels
    for i in range(len(model_names)):
        cell = table[i + 1, -1]
        cell.set_facecolor("#F3F4F6")
        cell.set_text_props(fontweight="bold")

    # Highlight best values per column
    for j, key in enumerate(METRIC_KEYS):
        vals = [metrics[name].get(key, 0) for name in model_names]
        best_idx = int(np.argmin(vals)) if key == "hamming_loss" else int(np.argmax(vals))
        cell = table[best_idx + 1, j]
        cell.set_facecolor("#DCFCE7")
        cell.set_text_props(fontweight="bold", color="#166534")

    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [VIZ] {save_path}")


# Label Co-occurrence Heatmaps

def plot_label_cooccurrence(
    matrices: dict[str, np.ndarray],
    label_names: list[str],
    save_path: str,
) -> None:
    """Stacked heatmaps for label co-occurrences arranged in a 2x2 grid.

    Args:
        matrices: dict mapping title to binary label array of shape (N, L).
        label_names: Ordered label names.
        save_path: Output image path.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    n_plots = len(matrices)
    cols = 2
    rows = (n_plots + 1) // 2
    
    fig, axes = plt.subplots(rows, cols, figsize=(16, 8 * rows))
    axes = axes.flatten()

    for idx, (title, y_matrix) in enumerate(matrices.items()):
        ax = axes[idx]
        # Calculate co-occurrence matrix (L, N) @ (N, L) -> (L, L)
        co_occurrence = y_matrix.T @ y_matrix
        co_occurrence = co_occurrence.astype(int)
        
        # Zero out the diagonal for better visualization of co-occurrences
        np.fill_diagonal(co_occurrence, 0)
        
        sns.heatmap(
            co_occurrence,
            annot=True, fmt="d", cmap="YlGnBu",
            xticklabels=label_names, yticklabels=label_names,
            ax=ax,
            linewidths=0.5, linecolor="#E5E7EB",
        )
        ax.set_title(f"{title} Label Co-occurrence (Diagonal ignored)", fontsize=13, fontweight="bold", pad=10)
        ax.tick_params(axis='x', rotation=45)
        ax.tick_params(axis='y', rotation=0)

    # Hide any unused subplots
    for idx in range(n_plots, len(axes)):
        fig.delaxes(axes[idx])

    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [VIZ] {save_path}")


# Classification Reports
def plot_classification_reports(
    reports: dict[str, dict],
    label_names: list[str],
    output_dir: str,
) -> None:
    """Render classification reports as separate heatmaps.
    
    Highlights precision, recall, and f1-score for each label.
    
    Args:
        reports: dict mapping model name to its classification report dict.
        label_names: Ordered label names.
        output_dir: Output directory path.
    """
    os.makedirs(output_dir, exist_ok=True)

    for model_name, report in reports.items():
        fig, ax = plt.subplots(figsize=(8, 10))
        
        # Extract metrics for the actual labels (ignore accuracy, macro avg, weighted avg)
        data = []
        for label in label_names:
            if label in report:
                data.append([
                    report[label]["precision"],
                    report[label]["recall"],
                    report[label]["f1-score"]
                ])
            else:
                data.append([0.0, 0.0, 0.0])
                
        data_arr = np.array(data)
        
        sns.heatmap(
            data_arr,
            annot=True, fmt=".4f", cmap="Blues",
            xticklabels=["Precision", "Recall", "F1-Score"],
            yticklabels=label_names,
            ax=ax, vmin=0.0, vmax=1.0,
            linewidths=0.5, linecolor="#E5E7EB",
        )
        ax.set_title(f"{model_name} Classification Report", fontsize=14, fontweight="bold", pad=10)
        ax.tick_params(axis='x', rotation=0)
        ax.tick_params(axis='y', rotation=0)

        fig.tight_layout()
        save_path = os.path.join(output_dir, f"classification_report_{model_name.lower()}.png")
        fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"  [VIZ] {save_path}")
