"""Evaluation visualisations for the NER benchmark.

Three artefacts are produced after evaluation:

* ``per_class_metrics.png``  — precision / recall / F1 bar chart per entity type.
* ``confusion_matrix.png``  — token-level confusion matrix on the BIO label set
  (the ``O`` row/column dominates if included, so it is dropped).
* ``summary_table.png``     — a single-row table of the headline scalar metrics.

Together they cover the standard benchmark deliverables expected from a research
NER evaluation.
"""

from __future__ import annotations

import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def plot_per_class_metrics(report: dict, save_path: str) -> None:
    """Bar chart of precision / recall / F1 per entity type from a seqeval report."""
    classes = [k for k in report.keys()
               if k not in ("micro avg", "macro avg", "weighted avg")]
    if not classes:
        return

    metrics = ("precision", "recall", "f1-score")
    values = np.array([[report[c].get(m, 0.0) for m in metrics] for c in classes])
    x = np.arange(len(classes))
    width = 0.27
    colors = ("#3B82F6", "#10B981", "#8B5CF6")

    fig, ax = plt.subplots(figsize=(max(8, len(classes) * 1.6), 5.5))
    for i, (m, c) in enumerate(zip(metrics, colors)):
        bars = ax.bar(x + (i - 1) * width, values[:, i], width,
                      label=m.replace("-score", ""), color=c, edgecolor="white")
        for b, v in zip(bars, values[:, i]):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=8, color="#374151")
    ax.set_xticks(x)
    ax.set_xticklabels(classes, rotation=20, ha="right")
    ax.set_ylim(0, 1.10)
    ax.set_ylabel("Score")
    ax.set_title("Per-Entity Precision / Recall / F1", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, frameon=True)
    ax.grid(True, axis="y", alpha=0.2, linestyle="--")
    sns.despine(ax=ax)

    fig.tight_layout()
    _ensure_dir(save_path)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_confusion_matrix(
    true_seqs: list[list[str]],
    pred_seqs: list[list[str]],
    labels: list[str],
    save_path: str,
    *,
    drop_outside: bool = True,
) -> None:
    """Token-level confusion heatmap on the BIO label set.

    ``drop_outside=True`` removes the ``O`` row/column to emphasise on-entity
    confusion; the absolute counts of ``O→O`` would otherwise dominate.
    """
    keep = [l for l in labels if not (drop_outside and l == "O")]
    idx = {l: i for i, l in enumerate(keep)}
    mat = np.zeros((len(keep), len(keep)), dtype=np.int64)
    for t_seq, p_seq in zip(true_seqs, pred_seqs):
        for t, p in zip(t_seq, p_seq):
            if t in idx and p in idx:
                mat[idx[t], idx[p]] += 1

    row_sums = mat.sum(axis=1, keepdims=True).clip(min=1)
    norm = mat / row_sums

    fig, ax = plt.subplots(figsize=(max(7, len(keep) * 0.6), max(6, len(keep) * 0.6)))
    sns.heatmap(norm, annot=mat, fmt="d", cmap="Blues",
                xticklabels=keep, yticklabels=keep, ax=ax, vmin=0, vmax=1,
                cbar_kws={"label": "Row-normalised proportion"},
                linewidths=0.4, linecolor="#E5E7EB")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Gold")
    ax.set_title("Token-Level Confusion (O dropped)" if drop_outside
                 else "Token-Level Confusion", fontsize=13, fontweight="bold")
    plt.setp(ax.get_xticklabels(), rotation=40, ha="right")
    plt.setp(ax.get_yticklabels(), rotation=0)

    fig.tight_layout()
    _ensure_dir(save_path)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_summary_table(metrics: dict, save_path: str) -> None:
    """Render the headline scalar metrics as an image-friendly table."""
    keys = ("n_test", "token_accuracy",
            "precision_macro", "recall_macro", "f1_macro",
            "precision_micro", "recall_micro", "f1_micro")
    rows = [[k, f"{metrics[k]:.4f}" if isinstance(metrics.get(k), float)
             else str(metrics.get(k, "—"))] for k in keys if k in metrics]

    fig, ax = plt.subplots(figsize=(7, 0.5 + 0.45 * len(rows)))
    ax.axis("off")
    tbl = ax.table(cellText=rows, colLabels=("Metric", "Value"),
                   loc="center", cellLoc="left")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1.0, 1.6)
    for j in range(2):
        tbl[0, j].set_facecolor("#E5E7EB")
        tbl[0, j].set_text_props(fontweight="bold")
    ax.set_title("Test-Set Benchmark Summary", fontsize=13, fontweight="bold", pad=14)

    fig.tight_layout()
    _ensure_dir(save_path)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
