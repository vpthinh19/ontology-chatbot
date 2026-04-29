"""Final Evaluation — multiclass classifier.

Evaluates fine-tuned PhoBERT multiclass models on the held-out test set:
    - Benchmark comparison (bar chart)
    - Summary table (all metrics x all models)
    - Classification reports
    - Label co-occurrence heatmap (one-hot for multiclass)
    - UMAP: Base vs fine-tuned test embeddings

Usage:
    python -m src.scripts.evaluate
"""

from __future__ import annotations

import os

import numpy as np
import torch
from datasets import load_dataset
from sklearn.metrics import classification_report
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer

from ..core.config import (
    BATCH_SIZE,
    EVAL_OUTPUT_DIR,
    LABEL_MAP_PATH,
    MAX_LENGTH,
    MODEL_ASL_DIR,
    MODEL_BCE_DIR,
    MODEL_NAME,
    MODEL_ZLPR_DIR,
    TEST_DATASET_PATH,
)
from ..utils.labels import load_label_names
from ..utils.preprocessing import preprocess_batch
from ..utils.inference import extract_embeddings, get_logits
from ..utils.metrics import compute_metrics
from ..viz import (
    plot_classification_reports,
    plot_label_cooccurrence,
    plot_metrics_comparison,
    plot_summary_table,
    plot_umap_comparison,
)


# Model registry: (display_name, model_dir)
_MODELS: list[tuple[str, str]] = [
    ("BCE", MODEL_BCE_DIR),
    ("ASL", MODEL_ASL_DIR),
    ("ZLPR", MODEL_ZLPR_DIR),
]


def main() -> None:
    os.makedirs(EVAL_OUTPUT_DIR, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Loading Test Data...")

    label_names = load_label_names(LABEL_MAP_PATH)
    label_to_id = {name: i for i, name in enumerate(label_names)}
    num_labels = len(label_names)

    test_dataset = load_dataset("json", data_files={"test": TEST_DATASET_PATH})["test"]
    test_labels_raw = test_dataset["label"]

    tokenizer = AutoTokenizer.from_pretrained(MODEL_BCE_DIR)

    def process_batch(examples):
        texts = preprocess_batch(examples["text"], word_segmentation=True)
        tokenized = tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
        )
        label_ids = [label_to_id[lbl] for lbl in examples["label"]]
        tokenized["labels"] = label_ids
        return tokenized

    cols_to_remove = test_dataset.column_names
    test_dataset = test_dataset.map(
        process_batch, batched=True, batch_size=1000, remove_columns=cols_to_remove
    )
    test_dataset.set_format("torch")

    y_test = test_dataset["labels"][:].detach().cpu().numpy().astype(np.int64)

    print(f"  Test samples: {len(test_dataset)}")
    print(f"  Labels: {num_labels}")

    # Inference and metrics
    print("Inference on Test Set...")

    logits_dict: dict[str, np.ndarray] = {}
    preds: dict[str, np.ndarray] = {}
    embeddings: dict[str, np.ndarray] = {}
    all_metrics: dict[str, dict[str, float]] = {}

    print("  Extracting base PhoBERT embeddings ...")
    base_model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    embeddings["Base PhoBERT"] = extract_embeddings(base_model, test_dataset, batch_size=BATCH_SIZE)
    del base_model
    torch.cuda.empty_cache()

    for name, model_dir in _MODELS:
        print(f"\n  Evaluating {name} model from: {model_dir}")
        model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(device)

        logits_dict[name] = get_logits(model, test_dataset, batch_size=BATCH_SIZE)
        preds[name] = np.argmax(logits_dict[name], axis=-1).astype(np.int64)

        # Metrics
        all_metrics[name] = compute_metrics(logits_dict[name], y_test)

        # Embeddings
        print(f"  Extracting {name} fine-tuned embeddings ...")
        embeddings[f"{name} Fine-tuned"] = extract_embeddings(model, test_dataset, batch_size=BATCH_SIZE)

        del model
        torch.cuda.empty_cache()

    # Metrics comparison
    print("Test Metrics...")

    metric_keys = list(next(iter(all_metrics.values())).keys())
    model_names = list(all_metrics.keys())
    header = f"  {'Metric':<25}" + "".join(f" {n:>12}" for n in model_names)
    print(f"\n{header}")
    print("  " + "-" * (25 + 13 * len(model_names)))
    for key in metric_keys:
        row = f"  {key:<25}"
        for name in model_names:
            row += f" {all_metrics[name][key]:>12.4f}"
        print(row)

    plot_metrics_comparison(
        all_metrics,
        os.path.join(EVAL_OUTPUT_DIR, "test_metrics_comparison.png"),
        title="Test Set Benchmark",
    )

    plot_summary_table(
        all_metrics,
        os.path.join(EVAL_OUTPUT_DIR, "test_summary_table.png"),
        title="Test Set Summary",
    )

    # Classification reports (multiclass)
    print("Generating Classification Reports...")

    reports: dict[str, dict] = {}
    for name in model_names:
        reports[name] = classification_report(
            y_test,
            preds[name],
            target_names=label_names,
            zero_division=0,
            output_dict=True,
        )

    plot_classification_reports(
        reports,
        label_names,
        EVAL_OUTPUT_DIR,
    )

    # Label co-occurrence heatmaps (one-hot for multiclass)
    print("Plotting Label Co-occurrence Heatmaps...")

    y_true_onehot = np.eye(num_labels, dtype=int)[y_test]
    matrices = {"Ground Truth": y_true_onehot}
    for name in model_names:
        y_pred_onehot = np.eye(num_labels, dtype=int)[preds[name]]
        matrices[f"{name} Predictions"] = y_pred_onehot

    plot_label_cooccurrence(
        matrices,
        label_names,
        os.path.join(EVAL_OUTPUT_DIR, "cooccurrence_all.png"),
    )

    # UMAP: base vs fine-tuned on test data
    print("Plotting UMAP - Test Embeddings...")

    plot_umap_comparison(
        embeddings,
        [[l] for l in test_labels_raw],  # labels_list: List[List[str]]
        label_names,
        os.path.join(EVAL_OUTPUT_DIR, "umap_test_comparison.png"),
        suptitle="UMAP -- Test Set Embeddings",
    )

    print(f"\n  All results saved to: {EVAL_OUTPUT_DIR}")
    print("\nDone!")


if __name__ == "__main__":
    main()
