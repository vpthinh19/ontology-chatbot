"""Kiểu vẽ dùng chung cho mọi biểu đồ trong README."""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RA = Path("docs/images")
RA.mkdir(parents=True, exist_ok=True)

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
