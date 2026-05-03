"""Dataset-level visualisations.

Two artefacts are produced once the dataset is built:

* ``label_distribution.png``  — count of entity occurrences per NER tag and the
  proportion of entity-bearing samples per split.
* ``length_distribution.png`` — histogram of token-sequence lengths, indicating
  how often the configured ``MAX_LENGTH`` is approached or exceeded.
"""

from __future__ import annotations

import os
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns


def _entity_counts(rows: list[dict]) -> Counter[str]:
    out: Counter[str] = Counter()
    for r in rows:
        for t in r["ner_tags"]:
            if t.startswith("B-"):
                out[t[2:]] += 1
    return out


def _no_entity_share(rows: list[dict]) -> float:
    n = len(rows)
    if not n:
        return 0.0
    blank = sum(1 for r in rows if all(t == "O" for t in r["ner_tags"]))
    return blank / n


def plot_label_distribution(
    splits: dict[str, list[dict]],
    save_path: str,
) -> None:
    """Stacked bar chart of B-tag counts per split (one bar group per tag)."""
    counts = {name: _entity_counts(rows) for name, rows in splits.items()}
    tags = sorted({t for c in counts.values() for t in c})
    if not tags:
        return
    x = np.arange(len(tags))
    width = 0.8 / max(1, len(splits))
    palette = sns.color_palette("Set2", n_colors=len(splits))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5),
                             gridspec_kw={"width_ratios": [3, 1]})
    ax = axes[0]
    for i, (name, rows) in enumerate(splits.items()):
        vals = [counts[name].get(t, 0) for t in tags]
        bars = ax.bar(x + (i - (len(splits) - 1) / 2) * width, vals, width,
                      label=name, color=palette[i], edgecolor="white")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.5,
                    str(v), ha="center", va="bottom", fontsize=8, color="#374151")
    ax.set_xticks(x)
    ax.set_xticklabels(tags, rotation=20, ha="right")
    ax.set_ylabel("Entity occurrences")
    ax.set_title("Entity Distribution by Tag", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, frameon=True)
    ax.grid(True, axis="y", alpha=0.2, linestyle="--")
    sns.despine(ax=ax)

    ax2 = axes[1]
    names = list(splits.keys())
    shares = [_no_entity_share(splits[n]) for n in names]
    bars = ax2.bar(names, shares, color=palette[: len(names)], edgecolor="white")
    for b, s in zip(bars, shares):
        ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.01,
                 f"{s:.2%}", ha="center", va="bottom", fontsize=9, color="#374151")
    ax2.set_ylim(0, max(shares) * 1.25 + 0.05 if shares else 1)
    ax2.set_ylabel("Share of all-O samples")
    ax2.set_title("Non-Entity Sample Share", fontsize=12, fontweight="bold")
    ax2.grid(True, axis="y", alpha=0.2, linestyle="--")
    sns.despine(ax=ax2)

    fig.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_length_distribution(
    splits: dict[str, list[dict]],
    save_path: str,
    *,
    max_length: int | None = None,
) -> None:
    """Histogram of token-sequence lengths overlaid for each split."""
    fig, ax = plt.subplots(figsize=(11, 5))
    palette = sns.color_palette("Set2", n_colors=len(splits))
    lengths_all: list[int] = []
    for (name, rows), color in zip(splits.items(), palette):
        lengths = [len(r["tokens"]) for r in rows]
        lengths_all.extend(lengths)
        ax.hist(lengths, bins=20, alpha=0.55, label=f"{name} (n={len(rows)})",
                color=color, edgecolor="white")
    if max_length is not None:
        ax.axvline(max_length, color="#EF4444", linestyle="--",
                   label=f"MAX_LENGTH = {max_length}")
    ax.set_xlabel("Tokens per sample")
    ax.set_ylabel("Count")
    ax.set_title("Sequence-Length Distribution", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, frameon=True)
    ax.grid(True, axis="y", alpha=0.2, linestyle="--")
    sns.despine(ax=ax)

    fig.tight_layout()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    fig.savefig(save_path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
