"""Kiểu vẽ dùng chung cho mọi biểu đồ trong README."""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RA = Path("docs/images")
RA.mkdir(parents=True, exist_ok=True)

# Mỗi mô hình giữ đúng một màu ở mọi biểu đồ, để người đọc không phải dò chú giải lại.
MAU = {"t5gemma2": "#1f4e79", "mbart": "#2e8b8b", "bartpho": "#d99b30", "vit5": "#b3543f"}
THUTU = ("t5gemma2", "mbart", "bartpho", "vit5")
NHAN = {"t5gemma2": "T5Gemma-2", "mbart": "mBART", "bartpho": "BARTpho", "vit5": "ViT5"}
NEN = "#f7f5f2"
MUC = "#2b2b2b"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.edgecolor": "#c9c4bd",
    "axes.facecolor": "white",
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": "#e3ded7",
    "grid.linewidth": 0.8,
    "figure.facecolor": "white",
    "legend.frameon": False,
    "xtick.color": MUC, "ytick.color": MUC, "text.color": MUC,
    "axes.labelcolor": MUC,
})


def khung(w=9.0, h=5.0):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


def luu(fig, ten: str) -> None:
    duong = RA / ten
    fig.tight_layout()
    fig.savefig(duong, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("   ", duong)


def nhan_cot(ax, thanh, dinh_dang="{:.0f}%", lech=1.0, co=9):
    for t in thanh:
        cao = t.get_height()
        ax.text(t.get_x() + t.get_width() / 2, cao + lech, dinh_dang.format(cao),
                ha="center", va="bottom", fontsize=co, color=MUC)


def doc_ca_bon(ten_tep="benchmark-test.json"):
    """Kết quả từng câu của cả bốn mô hình."""
    ra = {}
    for m in THUTU:
        ra[m] = json.loads(Path(f"artifacts/training-results/{m}/{ten_tep}").read_text())
    return ra


def bao_cao():
    return json.loads(Path("artifacts/training-results/report/models.json").read_text())
