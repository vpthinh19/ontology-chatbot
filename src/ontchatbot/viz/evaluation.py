"""Evaluation visualisations for the NER benchmark.

Three artefacts:

* ``classification_report.png`` — table chart with per-entity precision /
  recall / F1 / support rows, plus the standard micro / macro / weighted
  averages, and a final accent row that surfaces the token-level accuracy.
  This single chart subsumes the old text classification report, the
  per-class metrics bar chart, and the JSON metrics dump.

* ``confusion_matrix.png`` — token-level BIO confusion (``O`` dropped).

* ``comparison.png`` — grouped bar chart over token-accuracy + macro
  precision/recall/F1 for an arbitrary set of named models (used to put the
  fine-tuned checkpoint next to the untrained-head baseline in a single view).
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


# Classification-report table (subsumes per-class bars + benchmark card +
# the legacy text report).

_HEADER_FILL = "#1F2937"
_HEADER_TEXT = "#FFFFFF"
_AVG_FILL = "#EEF2FF"          # lavender for the avg rows
_ACCURACY_FILL = "#10B981"     # accent green for the final accuracy row
_ACCURACY_TEXT = "#FFFFFF"
_ENTITY_FILL = "#FFFFFF"
_GRID_COLOR = "#D1D5DB"


def _fmt_metric(value: float) -> str:
    return f"{value:.4f}"


def _fmt_int(value: int | float | None) -> str:
    return "—" if value is None else f"{int(value)}"


def plot_classification_report(
    dict_report: dict,
    accuracy: float,
    save_path: str,
    *,
    title: str = "PhoBERT NER — Classification Report",
) -> None:
    """Render seqeval's ``output_dict=True`` report as a styled table chart.

    The chart layout mirrors the textual report (entity rows on top,
    micro/macro/weighted averages below) and ends with a single accent row
    for token-level accuracy — keeping the table self-contained so a reader
    no longer needs the JSON metrics dump.
    """
    avg_keys = ("micro avg", "macro avg", "weighted avg")
    entity_keys = [k for k in dict_report.keys() if k not in avg_keys]
    entity_keys.sort()

    rows: list[tuple[str, list[str], str, str]] = []  # (label, cells, fill, text_color)
    headers = ["Entity", "Precision", "Recall", "F1-score", "Support"]

    for k in entity_keys:
        r = dict_report[k]
        rows.append((
            k,
            [_fmt_metric(r.get("precision", 0.0)),
             _fmt_metric(r.get("recall", 0.0)),
             _fmt_metric(r.get("f1-score", 0.0)),
             _fmt_int(r.get("support", 0))],
            _ENTITY_FILL, "#111827",
        ))
    for k in avg_keys:
        if k not in dict_report:
            continue
        r = dict_report[k]
        rows.append((
            k,
            [_fmt_metric(r.get("precision", 0.0)),
             _fmt_metric(r.get("recall", 0.0)),
             _fmt_metric(r.get("f1-score", 0.0)),
             _fmt_int(r.get("support", 0))],
            _AVG_FILL, "#111827",
        ))
    rows.append((
        "token accuracy",
        ["—", "—", _fmt_metric(accuracy), "—"],
        _ACCURACY_FILL, _ACCURACY_TEXT,
    ))

    n_rows = len(rows)
    n_cols = len(headers)

    # Figure sizing — width is fixed to fit text, height scales with rows.
    fig_w = 11.5
    fig_h = 1.2 + 0.55 * n_rows
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # Title
    ax.text(0.5, 0.965, title, ha="center", va="center",
            fontsize=15, fontweight="bold", color="#111827",
            transform=ax.transAxes)

    # Layout — first column wider (entity names), the four metric columns equal.
    col_widths = np.array([0.34, 0.16, 0.16, 0.16, 0.18])
    col_lefts = np.concatenate([[0.0], np.cumsum(col_widths)[:-1]])

    # Rows occupy from y=0 (bottom) up to y=0.92, leaving space for the title.
    body_top = 0.90
    body_bot = 0.04
    row_h = (body_top - body_bot) / (n_rows + 1)  # +1 for header

    def _draw_row(y_top: float, cells: list[str], *, fill: str, text_color: str,
                  bold: bool = False, header: bool = False) -> None:
        for i, (left, w, text) in enumerate(zip(col_lefts, col_widths, cells)):
            ax.add_patch(plt.Rectangle((left, y_top - row_h), w, row_h,
                                       facecolor=fill, edgecolor=_GRID_COLOR,
                                       linewidth=0.8, transform=ax.transAxes))
            ha = "left" if i == 0 else "center"
            x = left + (0.012 if i == 0 else w / 2)
            ax.text(x, y_top - row_h / 2, text, ha=ha, va="center",
                    fontsize=11, color=text_color,
                    fontweight=("bold" if bold or header else "normal"),
                    transform=ax.transAxes,
                    family=("DejaVu Sans Mono" if i > 0 and not header else "DejaVu Sans"))

    # Header
    _draw_row(body_top, headers, fill=_HEADER_FILL, text_color=_HEADER_TEXT, header=True)

    # Body rows
    for i, (label, cells, fill, color) in enumerate(rows):
        y_top = body_top - row_h * (i + 1)
        is_avg = label in avg_keys
        is_accuracy = label == "token accuracy"
        _draw_row(y_top, [label, *cells], fill=fill, text_color=color,
                  bold=is_avg or is_accuracy)

    _ensure_dir(save_path)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# Multi-model comparison (fine-tuned vs untrained-head baseline)

# Palette is intentionally aligned with the classification-report styling
# above: green for the model we are championing (the fine-tuned checkpoint),
# muted grey for the foil. Keeps the artefact set visually consistent.
_COMPARISON_PALETTE = {
    "finetuned": "#10B981",
    "baseline":  "#9CA3AF",
}
_COMPARISON_FALLBACK = ["#2563EB", "#F59E0B", "#EF4444"]


def plot_comparison(
    results: dict[str, tuple[float, dict]],
    save_path: str,
    *,
    title: str = "Fine-tuning impact on PhoBERT NER",
) -> None:
    """Grouped bar chart over (accuracy, macro precision, macro recall, macro F1).

    ``results`` is a dict ``{model_name: (token_accuracy, dict_report)}`` where
    ``dict_report`` is the ``output_dict=True`` form of
    :func:`seqeval.metrics.classification_report`. The "macro avg" row drives
    the precision/recall/F1 bars; the standalone accuracy float drives the
    first group. Order of bars within each metric group follows the iteration
    order of ``results`` — pass ``finetuned`` first so it sits on the left.
    """
    metric_labels = ["token accuracy", "precision (macro)", "recall (macro)", "F1 (macro)"]
    model_names = list(results.keys())

    values = np.zeros((len(model_names), len(metric_labels)), dtype=float)
    for i, name in enumerate(model_names):
        accuracy, dict_report = results[name]
        macro = dict_report.get("macro avg", {}) or {}
        values[i] = [
            accuracy,
            macro.get("precision", 0.0),
            macro.get("recall", 0.0),
            macro.get("f1-score", 0.0),
        ]

    n_models = len(model_names)
    width = 0.8 / max(n_models, 1)
    x = np.arange(len(metric_labels))

    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    for i, name in enumerate(model_names):
        offset = (i - (n_models - 1) / 2) * width
        color = _COMPARISON_PALETTE.get(
            name, _COMPARISON_FALLBACK[i % len(_COMPARISON_FALLBACK)]
        )
        bars = ax.bar(
            x + offset, values[i], width,
            label=name, color=color,
            edgecolor="#111827", linewidth=0.6,
        )
        for b, v in zip(bars, values[i]):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.012, f"{v:.3f}",
                    ha="center", va="bottom", fontsize=9, color="#111827")

    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=11)
    ax.set_ylim(0.0, 1.08)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold", color="#111827", pad=12)
    ax.legend(loc="upper right", frameon=False, fontsize=11)
    ax.grid(axis="y", alpha=0.3, linestyle="--", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    _ensure_dir(save_path)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
