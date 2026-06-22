"""Sinh TẤT CẢ Hình trực quan cho docs/CONCEPT.md (đánh giá mô hình + đối chứng).

    uv run --extra train python -m ontchatbot.scripts.visualize

Một lệnh sinh mọi Hình có thể (bỏ qua Hình thiếu nguồn, in cảnh báo):
* **Hình 8** ``training_curve.png`` — train/val loss theo bước, đọc ``config.TRAIN_LOG_PATH``
  (train.py lưu sau khi train). Thiếu log ⇒ bỏ qua (chạy train.py trước).
* **Hình 9** ``eval_per_category.png`` — F1 + exact-match theo loại câu, đọc ``eval_report.json``.
* **Hình 10** ``intent_confusion.png`` — ma trận nhầm lẫn trường ``act``, đọc ``eval_report.json``
  (cần field ``act_confusion`` — evaluate.py phiên mới ghi; report cũ thiếu thì bỏ qua).
* **Hình 13/14** benchmark — uỷ thác ``baseline.figures`` nếu có ``benchmark_report.json``.

Tách khỏi ``baseline/figures.py`` (đối chứng) vì đây là viz cho khâu đánh giá mô hình. Cả hai ghi
vào ``config.FIGURES_DIR`` (= docs/figures/, đã bỏ ignore để CONCEPT.md nhúng được).
"""

from __future__ import annotations

import json

from ..capabilities import GROUP_KEYS, GROUP_LABEL
from ..config import EVAL_ARTIFACTS_DIR, FIGURES_DIR, TRAIN_LOG_PATH

# Hình 9 báo theo NHÓM NĂNG LỰC (5 nhóm, độ khó tăng dần) rồi tới các loại phi-truy-vấn.
_ORDER = GROUP_KEYS + ["neg_child_miss", "neg_root_vague", "greeting", "ood", "vague"]
_LABELS = {**GROUP_LABEL,
           "neg_child_miss": "Thiếu (con)", "neg_root_vague": "Mơ hồ (gốc)",
           "greeting": "Chào hỏi", "ood": "Ngoài tri thức", "vague": "Mơ hồ"}
_ACTS = ["query", "greeting", "ood", "vague"]
_ACT_LABELS = {"query": "truy vấn", "greeting": "chào", "ood": "ngoài tri thức", "vague": "mơ hồ"}


def _training_curve() -> bool:
    if not TRAIN_LOG_PATH.exists():
        print(f"[viz] ⚠️ bỏ Hình 8 — thiếu {TRAIN_LOG_PATH} (chạy train.py trước để có log)")
        return False
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hist = json.loads(TRAIN_LOG_PATH.read_text(encoding="utf-8"))
    tr = [(h["step"], h["loss"]) for h in hist if "loss" in h and "eval_loss" not in h]
    ev = [(h["step"], h["eval_loss"]) for h in hist if "eval_loss" in h]
    fig, ax = plt.subplots(figsize=(8, 5))
    if tr:
        ax.plot(*zip(*tr), label="train loss", color="#2b6cb0", alpha=0.8)
    if ev:
        ax.plot(*zip(*ev), label="validation loss", color="#dd8452", marker="o", ms=3)
    ax.set_xlabel("bước huấn luyện")
    ax.set_ylabel("loss")
    ax.set_title("Hình 8. Đường cong huấn luyện (train vs validation loss)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "training_curve.png", dpi=150)
    plt.close(fig)
    print(f"[viz] → {FIGURES_DIR / 'training_curve.png'}")
    return True


def _eval_per_category(rep: dict) -> bool:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    per = rep["per_type"]
    cats = [c for c in _ORDER if c in per] + [c for c in per if c not in _ORDER]
    labels = [_LABELS.get(c, c) for c in cats]
    f1 = [per[c]["f1"] for c in cats]
    exact = [per[c]["exact_set"] for c in cats]
    x = np.arange(len(cats))
    w = 0.4
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.bar(x - w / 2, f1, w, label="F1 (đầu-cuối)", color="#2b6cb0")
    ax.bar(x + w / 2, exact, w, label="Exact-match", color="#55a868")
    ax.set_ylabel("Điểm")
    ax.set_ylim(0, 1.05)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_title("Hình 9. F1 và trùng-khít-tập theo nhóm năng lực (đánh giá đầu-cuối)")
    ax.legend(loc="lower left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "eval_per_category.png", dpi=150)
    plt.close(fig)
    print(f"[viz] → {FIGURES_DIR / 'eval_per_category.png'}")
    return True


def _intent_confusion(rep: dict) -> bool:
    conf = rep.get("act_confusion")
    if not conf:
        print("[viz] ⚠️ bỏ Hình 10 — eval_report.json thiếu 'act_confusion' (chạy lại evaluate.py mới)")
        return False
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    acts = [a for a in _ACTS if a in conf or any(a in d for d in conf.values())]
    mat = np.array([[conf.get(g, {}).get(p, 0) for p in acts] for g in acts], dtype=float)
    row = mat.sum(axis=1, keepdims=True)
    norm = np.divide(mat, row, out=np.zeros_like(mat), where=row > 0)   # tô màu theo tỉ lệ hàng
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(acts)), [_ACT_LABELS.get(a, a) for a in acts], rotation=20, ha="right")
    ax.set_yticks(range(len(acts)), [_ACT_LABELS.get(a, a) for a in acts])
    ax.set_xlabel("act dự đoán")
    ax.set_ylabel("act đúng (gold)")
    ax.set_title("Hình 10. Ma trận nhầm lẫn trường act")
    for i in range(len(acts)):
        for j in range(len(acts)):
            ax.text(j, i, int(mat[i, j]), ha="center", va="center",
                    color="white" if norm[i, j] > 0.5 else "black")
    fig.colorbar(im, ax=ax, label="tỉ lệ theo hàng")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "intent_confusion.png", dpi=150)
    plt.close(fig)
    print(f"[viz] → {FIGURES_DIR / 'intent_confusion.png'}")
    return True


def make_eval_figures() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    report_path = EVAL_ARTIFACTS_DIR / "eval_report.json"
    _training_curve()
    if report_path.exists():
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        _eval_per_category(rep)
        _intent_confusion(rep)
    else:
        print(f"[viz] ⚠️ bỏ Hình 9/10 — thiếu {report_path} (chạy evaluate.py trước)")


def main() -> None:
    make_eval_figures()
    # Uỷ thác Hình benchmark (14/15) nếu đã có kết quả benchmark.
    if (EVAL_ARTIFACTS_DIR / "benchmark_report.json").exists():
        from ..baseline.figures import make_figures
        make_figures()
    else:
        print("[viz] ⚠️ bỏ Hình 13/14 — thiếu benchmark_report.json (chạy baseline.benchmark trước)")


if __name__ == "__main__":
    main()
