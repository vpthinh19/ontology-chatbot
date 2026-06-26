"""Sinh Hình kết quả benchmark cho docs/CONCEPT.md.

    uv run --extra train python -m ontchatbot.baseline.figures

Đọc ``artifacts/evaluation/benchmark_report.json`` (đã gom theo NHÓM NĂNG LỰC, một phẳng) → 2 PNG:
* ``benchmark_per_type.png`` (Hình 13): chất lượng theo nhóm năng lực - ontology (F1) vs phẳng (recall@3).
* ``recall_at_k.png`` (Hình 14): đường recall@k của phẳng (k=1/3/5) + mốc recall ontology.
"""

from __future__ import annotations

import json
import sys

from ..config import EVAL_ARTIFACTS_DIR, FIGURES_DIR
from .groups import GROUP_KEYS, GROUP_LABEL

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_FLAT_COLOR = "#dd8452"
_ONT_COLOR = "#2b6cb0"


def _load() -> dict:
    return json.loads((EVAL_ARTIFACTS_DIR / "benchmark_report.json").read_text(encoding="utf-8"))


def make_figures() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    rep = _load()
    per = rep["per_type"]
    groups = [g for g in GROUP_KEYS if g in per]
    labels = [GROUP_LABEL.get(g, g) for g in groups]
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # Hình 13: chất lượng theo nhóm năng lực - ontology F1 vs phẳng recall@3
    ont_f1 = [per[g]["ontology"]["f1"] for g in groups]
    flat_recall = [per[g]["flat"].get("recall@3", 0.0) for g in groups]
    x = np.arange(len(groups))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - w / 2, ont_f1, w, label="Ontology (F1)", color=_ONT_COLOR)
    ax.bar(x + w / 2, flat_recall, w, label="Phẳng (recall@3)", color=_FLAT_COLOR)
    ax.set_ylabel("Điểm")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_title("Hình 13. Chất lượng theo nhóm năng lực - ontology (F1) vs phẳng (recall@3)")
    ax.legend(loc="lower left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "benchmark_per_type.png", dpi=150)
    plt.close(fig)

    # Hình 14: đường recall@k của phẳng + mốc ontology
    ks = rep["config"]["ks"]
    fo = rep["overall"]["flat"]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(ks, [fo[f"recall@{k}"] for k in ks], marker="o", label="Phẳng", color=_FLAT_COLOR)
    ax.axhline(rep["overall"]["ontology"]["recall"], ls="--", color=_ONT_COLOR,
               label="Ontology (recall, trả khít)")
    ax.set_xlabel("k (số tài liệu trả về)")
    ax.set_ylabel("Recall@k (trung bình theo câu)")
    ax.set_xticks(ks)
    ax.set_ylim(0, 1.05)
    ax.set_title("Hình 14. Đường recall@k của hệ phẳng so với mốc ontology")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "recall_at_k.png", dpi=150)
    plt.close(fig)
    print(f"[figures] {FIGURES_DIR / 'benchmark_per_type.png'} + recall_at_k.png")


if __name__ == "__main__":
    make_figures()
