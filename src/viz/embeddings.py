"""UMAP embedding visualizations for model comparison."""

from __future__ import annotations

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns


def plot_umap_comparison(
    embeddings_dict: dict[str, np.ndarray],
    labels_list: list[list[str]],
    label_names: list[str],
    save_path: str,
    suptitle: str = "UMAP Comparison",
) -> None:
    """Side-by-side UMAP projections for multiple models.

    Supports a 2x2 grid layout.

    Args:
        embeddings_dict: {model_name: embedding_array}.
        labels_list: Per-sample label lists (plotting all labels).
        label_names: Ordered label names.
        save_path: Output image path.
        suptitle: Figure super-title.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    from umap import UMAP

    cols = 2
    rows = (len(embeddings_dict) + 1) // 2
    
    fig, axes = plt.subplots(rows, cols, figsize=(16, 8 * rows))
    axes = axes.flatten()

    palette = sns.color_palette("husl", n_colors=len(label_names))
    colour = {label: palette[i] for i, label in enumerate(label_names)}

    for idx, (name, emb) in enumerate(embeddings_dict.items()):
        # n_jobs=1 explicitly to suppress warning when random_state is set
        reducer = UMAP(
            n_components=2, random_state=42,
            n_neighbors=15, min_dist=0.1, n_jobs=1,
        )
        coords = reducer.fit_transform(emb)

        ax = axes[idx]
        
        # Plot all labels (points with multiple labels will be plotted multiple times)
        for label in label_names:
            lidx = [i for i, ls in enumerate(labels_list) if label in ls]
            if not lidx:
                continue
            ax.scatter(
                coords[lidx, 0], coords[lidx, 1],
                c=[colour[label]], label=label,
                alpha=0.65, s=20, edgecolors="white", linewidth=0.3,
            )
            
        ax.set_title(name, fontsize=14, fontweight="bold")
        ax.set_xlabel("UMAP 1", fontsize=11)
        ax.set_ylabel("UMAP 2", fontsize=11)
        ax.tick_params(labelsize=9)
        sns.despine(ax=ax)

    # Hide any unused subplots
    for idx in range(len(embeddings_dict), len(axes)):
        fig.delaxes(axes[idx])

    # Single shared legend from the first ax
    handles, leg_labels = axes[0].get_legend_handles_labels()
    # We might have duplicate labels because we loop over labels_list, 
    # but since we loop over `label_names` to scatter, `handles` and `leg_labels` are unique.
    fig.legend(
        handles, leg_labels,
        bbox_to_anchor=(1.01, 0.5), loc="center left",
        fontsize=10, markerscale=1.8, frameon=True, fancybox=True,
        title="Labels", title_fontsize=12,
    )

    fig.suptitle(suptitle, fontsize=18, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(save_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [VIZ] {save_path}")
