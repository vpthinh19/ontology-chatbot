"""Sinh Hình kết quả benchmark cho docs/CONCEPT.md (Phase 8).

    uv run --extra train python -m ontchatbot.baseline.figures

Đọc ``artifacts/evaluation/benchmark_report.json`` → 2 hình PNG ở ``docs/figures/``:
* ``benchmark_per_type.png`` (Hình 13): recall theo từng loại câu — ontology vs phẳng concise/denorm.
  Dùng RECALL (cả hai = tỷ lệ tìm được gold) cho công bằng; precision@k của phẳng thấp cơ học (trả k
  phiếu cho câu 1-đáp-án) nên không làm trục headline. Ontology còn đạt precision/exact cao (trả KHÍT).
* ``recall_at_k.png`` (Hình 14): đường recall@k của phẳng (k=1/3/5) + mốc recall ontology — phơi hạn
  chế "phải đoán k" và việc phẳng vẫn dưới ontology dù tăng k.
"""

from __future__ import annotations

import json

from ..config import EVAL_ARTIFACTS_DIR, FIGURES_DIR

# thứ tự trình bày: nhóm tra-cứu-đơn trước, nhóm có-cấu-trúc sau (để thấy gradient khó dần)
_ORDER = ["self_desc", "data_leaf", "fee_data", "fee_intersect", "fee_cohort", "fee_major",
          "fee_union", "forward_object", "multi_field", "multi_hop"]
_LABELS = {
    "self_desc": "Tự mô tả", "data_leaf": "Thuộc tính", "fee_data": "HP/tín chỉ",
    "fee_intersect": "HP (giao)", "fee_cohort": "HP (khoá)", "fee_major": "HP (ngành)",
    "fee_union": "HP (gộp)", "forward_object": "Đi 1 quan hệ", "multi_field": "Nhiều thuộc tính",
    "multi_hop": "Đi nhiều bước",
}


def _load() -> dict:
    return json.loads((EVAL_ARTIFACTS_DIR / "benchmark_report.json").read_text(encoding="utf-8"))


def make_figures() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    rep = _load()
    per = rep["per_type"]
    cats = [c for c in _ORDER if c in per]
    labels = [_LABELS.get(c, c) for c in cats]
    variants = list(next(iter(per.values()))["flat"].keys())
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # ── Hình 13: recall theo loại câu ──
    ont_recall = [per[c]["ontology"]["recall"] for c in cats]
    flat_recall = {v: [per[c]["flat"][v]["recall@3"] for c in cats] for v in variants}
    x = np.arange(len(cats))
    nbar = 1 + len(variants)
    w = 0.8 / nbar
    flat_colors = {"concise": "#dd8452", "denorm": "#55a868"}
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - w * (nbar - 1) / 2, ont_recall, w, label="Ontology (recall)", color="#2b6cb0")
    for i, v in enumerate(variants, start=1):
        ax.bar(x - w * (nbar - 1) / 2 + i * w, flat_recall[v], w,
               label=f"Phẳng {v} (recall@3)", color=flat_colors.get(v))
    ax.set_ylabel("Recall")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_title("Hình 13. Recall theo loại câu hỏi — ontology vs cơ sở dữ liệu phẳng")
    ax.legend(loc="lower left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "benchmark_per_type.png", dpi=150)
    plt.close(fig)

    # ── Hình 14: đường recall@k ──
    ks = rep["config"]["ks"]
    fo = rep["overall"]["flat"]
    flat_colors = {"concise": "#dd8452", "denorm": "#55a868"}
    fig, ax = plt.subplots(figsize=(7, 5))
    for v in variants:
        ax.plot(ks, [fo[v][f"recall@{k}"] for k in ks], marker="o", label=f"Phẳng {v}",
                color=flat_colors.get(v))
    ax.axhline(rep["overall"]["ontology"]["recall"], ls="--", color="#2b6cb0",
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

    print(f"[figures] → {FIGURES_DIR / 'benchmark_per_type.png'}")
    print(f"[figures] → {FIGURES_DIR / 'recall_at_k.png'}")


if __name__ == "__main__":
    make_figures()
