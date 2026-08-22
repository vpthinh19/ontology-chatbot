"""Chấm điểm và vẽ hình cho các model phân loại.

Với 344 nhãn mà phần lớn chỉ có vài mẫu, accuracy bị các nhãn đông lấn át, nên mọi
bảng đều báo kèm trung bình vĩ mô - nơi một nhãn hai mẫu nặng ngang một nhãn chín
mươi mẫu. Bảng tách theo số mẫu huấn luyện có mặt vì đó là chỗ các model khác nhau
nhiều nhất.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from .classifier import ALL_MODELS, DISPLAY
from .labels import family_names, label_key, load_splits

BUCKETS = ("1-2", "3-4", "5-9", "10-19", "≥20")
METRIC_KEYS = ("accuracy", "macro_p", "macro_r", "macro_f1", "weighted_f1")
METRIC_TITLES = ("accuracy", "precision (macro)", "recall (macro)",
                 "F1 (macro)", "F1 (weighted)")


def available(out_dir: Path):
    return [t for t in ALL_MODELS if (out_dir / f"preds-{t}.npz").exists()]


def _bucket(n: int) -> str:
    return ("1-2" if n < 3 else "3-4" if n < 5 else "5-9" if n < 10
            else "10-19" if n < 20 else "≥20")


def measure(gold, pred) -> dict[str, float]:
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support

    out = {"accuracy": float(accuracy_score(gold, pred))}
    for average, keys in (("macro", ("macro_p", "macro_r", "macro_f1")),
                          ("weighted", ("weighted_p", "weighted_r", "weighted_f1"))):
        p, r, f, _ = precision_recall_fscore_support(
            gold, pred, average=average, zero_division=0)
        out.update(dict(zip(keys, (float(p), float(r), float(f)))))
    return out


def collect(out_dir: Path, split: str = "test"):
    """Chỉ số của mọi model đã huấn luyện, cùng dự đoán để phân tích thêm."""
    metrics, preds, gold = {}, {}, None
    for tag in available(out_dir):
        data = np.load(out_dir / f"preds-{tag}.npz", allow_pickle=True)
        gold = data[f"{split}_gold"]
        preds[DISPLAY[tag]] = data[f"{split}_pred"]
        metrics[DISPLAY[tag]] = measure(gold, preds[DISPLAY[tag]])
    return metrics, preds, gold


def report(out_dir: Path, split: str = "test") -> dict:
    rows, labels = load_splits()
    metrics, preds, gold = collect(out_dir, split)
    if not metrics:
        raise SystemExit("chưa có model nào được huấn luyện")

    print("=" * 78)
    print(f"CHỈ SỐ TRÊN TẬP {split.upper()} — {len(labels)} nhãn")
    print("=" * 78)
    for name, m in metrics.items():
        print(f"  {name:<16} acc {100*m['accuracy']:5.1f}%   "
              f"vĩ mô P/R/F1 {100*m['macro_p']:5.1f}/{100*m['macro_r']:5.1f}/"
              f"{100*m['macro_f1']:5.1f}   F1 trọng số {100*m['weighted_f1']:5.1f}")

    freq = Counter(r["y"] for r in rows["train"])
    print("\n" + "=" * 78)
    print("ĐỘ CHÍNH XÁC THEO SỐ MẪU HUẤN LUYỆN CỦA NHÃN ĐÚNG")
    print("=" * 78)
    print(f"  {'model':<16}" + "".join(f"{b:>10}" for b in BUCKETS))
    by_bucket = {}
    for name, pred in preds.items():
        hit, tot = Counter(), Counter()
        for g, p in zip(gold, pred):
            b = _bucket(freq.get(int(g), 0))
            tot[b] += 1
            hit[b] += int(g == p)
        by_bucket[name] = {b: (int(hit[b]), int(tot[b])) for b in BUCKETS}
        print(f"  {name:<16}" + "".join(
            f"{100*hit[b]/tot[b]:>9.0f}%" if tot[b] else f"{'-':>10}" for b in BUCKETS))

    best = max(metrics, key=lambda k: metrics[k]["accuracy"])
    print("\n" + "=" * 78)
    print(f"CẶP NHẦM NHIỀU NHẤT — {best}")
    print("=" * 78)
    keys = [label_key(l) for l in labels]
    pairs = Counter((int(g), int(p)) for g, p in zip(gold, preds[best]) if g != p)
    for (g, p), n in pairs.most_common(8):
        print(f"  {n}×  đúng: {keys[g][:40]:<42} → chọn: {keys[p][:40]}")

    payload = {"split": split, "labels": len(labels), "metrics": metrics,
               "by_training_count": by_bucket}
    json.dump(payload, open(out_dir / "benchmark-metrics.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nđã ghi {out_dir / 'benchmark-metrics.json'}")
    return payload


def figures(out_dir: Path, split: str = "test") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    from sklearn.metrics import confusion_matrix
    import umap

    # Ảnh của README phải nằm trong git, mà ``artifacts/`` thì không, nên bộ dựng
    # ghi thẳng vào thư mục ảnh của tài liệu.
    figure_dir = Path("docs/images")
    figure_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 8, "figure.dpi": 150,
                         "font.family": ["DejaVu Sans"],
                         "axes.grid": True, "grid.alpha": 0.25})
    palette = plt.get_cmap("tab10")

    names = family_names()
    metrics, preds, gold = collect(out_dir, split)
    tags = available(out_dir)
    best_tag = max(tags, key=lambda t: metrics[DISPLAY[t]]["accuracy"])
    data = np.load(out_dir / f"preds-{best_tag}.npz", allow_pickle=True)
    keys = list(data["labels"])

    def short(query_id, cap=52):
        name = names.get(query_id, query_id)
        return name if len(name) <= cap else name[: cap - 1] + "…"

    # Ma trận nhầm lẫn: 344 nhãn không đọc được nên gộp về nhóm câu hỏi.
    family_of = np.array([k.split("|")[0] for k in keys])
    groups = sorted(set(family_of))
    matrix = confusion_matrix([groups.index(family_of[g]) for g in gold],
                              [groups.index(family_of[p]) for p in preds[DISPLAY[best_tag]]],
                              labels=range(len(groups)))
    keep = [i for i in range(len(groups)) if matrix[i].sum() > 0]
    sub = matrix[np.ix_(keep, keep)]
    fig, ax = plt.subplots(figsize=(13, 11.5))
    image = ax.imshow(np.where(sub == 0, np.nan, sub), cmap="viridis", norm=LogNorm(vmin=1))
    ticks = [short(groups[i]) for i in keep]
    ax.set_xticks(range(len(keep)), ticks, rotation=90, fontsize=5.5)
    ax.set_yticks(range(len(keep)), ticks, fontsize=5.5)
    ax.set_xlabel("nhóm được chọn")
    ax.set_ylabel("nhóm đúng")
    ax.set_title(f"Ma trận nhầm lẫn — {DISPLAY[best_tag]}, tập {split} {len(gold)} câu\n"
                 f"gộp {len(keys)} nhãn về {len(keep)} nhóm có mặt trong tập", pad=12)
    ax.grid(False)
    plt.colorbar(image, ax=ax, shrink=0.5, label="số câu")
    plt.tight_layout()
    plt.savefig(figure_dir / "confusion-matrix.png")
    plt.close()

    # UMAP trên biểu diễn câu hỏi, tô theo nhóm lớn nhất.
    family = data[f"{split}_family"]
    top = [f for f, _ in Counter(family).most_common(8)]
    mask = np.isin(family, top)
    coords = umap.UMAP(n_neighbors=15, min_dist=0.1,
                       random_state=0).fit_transform(data[f"{split}_vec"])
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(coords[~mask, 0], coords[~mask, 1], s=7, c="#d5d5d5", linewidths=0,
               label=f"nhóm khác ({int((~mask).sum())} câu)")
    for k, f in enumerate(top):
        m = family == f
        ax.scatter(coords[m, 0], coords[m, 1], s=16, color=palette(k), linewidths=0,
                   label=f"{short(f, 38)} ({int(m.sum())})")
    ax.set_title(f"Biểu diễn câu hỏi tập {split} — {DISPLAY[best_tag]}\n"
                 "UMAP trên vector lấy trước lớp phân loại", pad=10)
    ax.legend(fontsize=6.5, markerscale=1.5, loc="upper left", bbox_to_anchor=(1.01, 1))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    plt.tight_layout()
    plt.savefig(figure_dir / "umap.png")
    plt.close()

    # Đường mất mát: baseline không có vòng epoch nên không xuất hiện ở đây.
    curves = [(t, json.load(open(out_dir / f"cls-{t}.json", encoding="utf-8")))
              for t in tags]
    curves = [(t, c) for t, c in curves if c["history"]]
    if curves:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        for k, (tag, cfg) in enumerate(curves):
            epochs = [h["epoch"] for h in cfg["history"]]
            axes[0].plot(epochs, [h["train_loss"] for h in cfg["history"]],
                         color=palette(k), label=DISPLAY[tag])
            axes[1].plot(epochs, [h["val_loss"] for h in cfg["history"]],
                         color=palette(k), label=DISPLAY[tag])
        for ax, title in zip(axes, ("training loss", "validation loss")):
            ax.set_xlabel("epoch")
            ax.set_ylabel("cross-entropy loss")
            ax.set_title(title)
            ax.legend(fontsize=7)
        plt.tight_layout()
        plt.savefig(figure_dir / "loss-curves.png")
        plt.close()

    # So sánh năm model trên cùng bộ chỉ số.
    fig, ax = plt.subplots(figsize=(10, 4.8))
    width = 0.8 / len(metrics)
    xs = np.arange(len(METRIC_KEYS))
    for k, (name, m) in enumerate(metrics.items()):
        bars = ax.bar(xs + k * width, [100 * m[key] for key in METRIC_KEYS],
                      width, label=name, color=palette(k))
        ax.bar_label(bars, fmt="%.1f", fontsize=6, padding=1)
    ax.set_xticks(xs + width * (len(metrics) - 1) / 2, METRIC_TITLES)
    ax.set_ylabel("%")
    ax.set_ylim(0, 100)
    ax.set_title(f"So sánh năm mô hình trên tập {split} — {len(keys)} nhãn", pad=10)
    ax.legend(fontsize=7, ncol=3)
    plt.tight_layout()
    plt.savefig(figure_dir / "model-comparison.png")
    plt.close()

    # Độ chính xác theo số mẫu huấn luyện: chỗ các model khác nhau nhiều nhất.
    payload = json.load(open(out_dir / "benchmark-metrics.json", encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(9, 4.4))
    xs = np.arange(len(BUCKETS))
    for k, (name, buckets) in enumerate(payload["by_training_count"].items()):
        vals = [100 * buckets[b][0] / buckets[b][1] if buckets[b][1] else np.nan
                for b in BUCKETS]
        ax.plot(xs, vals, marker="o", color=palette(k), label=name)
    # Ghi kèm số câu test của từng nhóm: nhóm nhỏ làm đường gãy mạnh, người đọc
    # cần thấy ngay là chênh lệch ở đó dựa trên rất ít câu.
    sizes = next(iter(payload["by_training_count"].values()))
    # Trục ngang gom nhãn theo số câu đã DẠY cho nhãn đó; con số trong ngoặc là số
    # câu CHẤM rơi vào nhóm. Hai thứ đều đếm bằng câu nên phải nói rõ từng cái, nếu
    # không người đọc tưởng chúng là một.
    ax.set_xticks(xs, [f"{b} câu dạy\n({sizes[b][1]} câu chấm)" for b in BUCKETS])
    ax.set_xlabel("nhãn được gom theo số câu đã dạy cho nhãn đó")
    ax.set_ylabel("accuracy (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Nhãn càng ít câu huấn luyện, các mô hình càng khác nhau", pad=10)
    ax.legend(fontsize=7)
    plt.tight_layout()
    plt.savefig(figure_dir / "accuracy-by-frequency.png")
    plt.close()

    print("đã dựng:", ", ".join(sorted(p.name for p in figure_dir.glob("*.png"))))
