"""Evaluation visualisations for the NER benchmark.

Three artefacts complement the textual ``classification_report.txt``:

* ``per_class_metrics.png`` — precision / recall / F1 bar chart per entity type.
* ``confusion_matrix.png``  — token-level BIO confusion (``O`` dropped).
* ``benchmark_card.png``    — a research-style summary card combining KPI
  tiles (test size, token accuracy, macro / micro F1) with a
  precision-recall scatter overlaid with iso-F1 contours.

The benchmark card is purposefully *not* a numeric table — that role is
already filled by the seqeval text report — but a graphical synthesis that
makes the macro vs micro gap and the per-class trade-offs immediately
legible.
"""

from __future__ import annotations

import os
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


# Per-class P/R/F1 bars

def plot_per_class_metrics(report: dict, save_path: str) -> None:
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


# Token-level confusion

def plot_confusion_matrix(
    true_seqs: list[list[str]],
    pred_seqs: list[list[str]],
    labels: Sequence[str],
    save_path: str,
    *,
    drop_outside: bool = True,
) -> None:
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


# Benchmark card — KPI tiles + P-R scatter with iso-F1 contours

def _kpi_tile(ax, label: str, value: str, *, accent: str) -> None:
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_facecolor("#F9FAFB")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes,
                               facecolor="#F9FAFB", edgecolor=accent, lw=2))
    ax.text(0.5, 0.66, value, ha="center", va="center",
            fontsize=26, fontweight="bold", color=accent,
            transform=ax.transAxes)
    ax.text(0.5, 0.22, label, ha="center", va="center",
            fontsize=11, color="#374151", transform=ax.transAxes)


def _draw_iso_f1(ax) -> None:
    """Overlay iso-F1 contours on a precision-recall axis."""
    p = np.linspace(0.01, 1, 200)
    r = np.linspace(0.01, 1, 200)
    P, R = np.meshgrid(p, r)
    F1 = 2 * P * R / (P + R + 1e-12)
    levels = [0.2, 0.4, 0.6, 0.8, 0.9]
    cs = ax.contour(P, R, F1, levels=levels, colors="#9CA3AF",
                    linestyles="--", linewidths=0.7, alpha=0.7)
    ax.clabel(cs, inline=True, fontsize=8,
              fmt={lv: f"F1={lv:.1f}" for lv in levels})


def plot_benchmark_card(
    metrics: dict,
    dict_report: dict,
    save_path: str,
) -> None:
    """Combined KPI + P-R scatter with iso-F1 contours."""
    classes = [k for k in dict_report.keys()
               if k not in ("micro avg", "macro avg", "weighted avg")]
    palette = sns.color_palette("Set2", n_colors=max(3, len(classes)))

    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 3], hspace=0.30, wspace=0.30)

    # KPI tiles
    tiles = [
        ("Test samples", str(metrics.get("n_test", "—")), "#1F2937"),
        ("Token accuracy", f"{metrics.get('token_accuracy', 0.0):.3f}", "#10B981"),
        ("F1-macro", f"{metrics.get('f1_macro', 0.0):.3f}", "#8B5CF6"),
        ("F1-micro", f"{metrics.get('f1_micro', 0.0):.3f}", "#3B82F6"),
    ]
    for i, (lbl, val, col) in enumerate(tiles):
        _kpi_tile(fig.add_subplot(gs[0, i]), lbl, val, accent=col)

    # Bottom panel: P-R scatter
    ax = fig.add_subplot(gs[1, :])
    _draw_iso_f1(ax)
    for i, c in enumerate(classes):
        p = dict_report[c].get("precision", 0.0)
        r = dict_report[c].get("recall", 0.0)
        sup = dict_report[c].get("support", 1) or 1
        size = 80 + 18 * np.sqrt(max(sup, 1))
        ax.scatter(p, r, s=size, color=palette[i], edgecolor="white",
                   linewidth=1.2, zorder=3, label=f"{c} (n={sup})")
        ax.annotate(c, (p, r), textcoords="offset points",
                    xytext=(8, 6), fontsize=9, color="#1F2937")

    # Macro / micro reference markers
    ax.scatter(metrics.get("precision_macro", 0.0),
               metrics.get("recall_macro", 0.0),
               marker="*", s=300, color="#8B5CF6", edgecolor="white",
               linewidth=1.5, zorder=4, label="macro avg")
    ax.scatter(metrics.get("precision_micro", 0.0),
               metrics.get("recall_micro", 0.0),
               marker="*", s=300, color="#3B82F6", edgecolor="white",
               linewidth=1.5, zorder=4, label="micro avg")

    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Precision", fontsize=12)
    ax.set_ylabel("Recall", fontsize=12)
    ax.set_title("Precision–Recall by Entity Type (dot size ∝ √support)",
                 fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.2, linestyle="--")
    ax.legend(fontsize=9, loc="lower left", frameon=True, ncol=2)
    sns.despine(ax=ax)

    fig.suptitle("PhoBERT NER — Test-Set Benchmark Card",
                 fontsize=15, fontweight="bold", y=0.98)
    _ensure_dir(save_path)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
