"""Benchmark the fine-tuned NER model on the held-out test split.

Reports ``seqeval`` entity-level metrics (strict BIO matching), which are the
de-facto academic standard for NER:

* Token-level accuracy (sub-word ignored)
* Entity-level precision / recall / F1 — both macro- and micro-averaged
* Per-entity-type classification report

Outputs in ``out/evaluation/``:
    test_metrics.json
    classification_report.txt
    per_class_metrics.png
    confusion_matrix.png
    summary_table.png
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from seqeval.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
)

from ..config import BATCH_SIZE, EVAL_OUT_DIR, MODEL_DIR, TEST_PATH
from ..viz.evaluation import (
    plot_confusion_matrix,
    plot_per_class_metrics,
    plot_summary_table,
)
from .dataset import label_mappings, load_split, make_tokenize_fn


def _predict(model, loader, device, i2l) -> tuple[list[list[str]], list[list[str]]]:
    true_seqs: list[list[str]] = []
    pred_seqs: list[list[str]] = []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            batch = {k: v.to(device) for k, v in batch.items()}
            preds = np.argmax(model(**batch).logits.cpu().numpy(), axis=-1)
            for p_row, l_row in zip(preds, labels.numpy()):
                t, p = [], []
                for pi, li in zip(p_row, l_row):
                    if li == -100:
                        continue
                    t.append(i2l[int(li)])
                    p.append(i2l[int(pi)])
                true_seqs.append(t)
                pred_seqs.append(p)
    return true_seqs, pred_seqs


def main() -> None:
    labels, l2i, i2l = label_mappings()
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    ds = load_split(TEST_PATH, l2i).map(
        make_tokenize_fn(tokenizer), batched=True, remove_columns=["tokens", "tags"]
    )
    loader = DataLoader(ds, batch_size=BATCH_SIZE,
                        collate_fn=DataCollatorForTokenClassification(tokenizer))

    true_seqs, pred_seqs = _predict(model, loader, device, i2l)

    metrics = {
        "n_test": len(true_seqs),
        "token_accuracy": accuracy_score(true_seqs, pred_seqs),
        "precision_macro": precision_score(true_seqs, pred_seqs, average="macro", zero_division=0),
        "recall_macro": recall_score(true_seqs, pred_seqs, average="macro", zero_division=0),
        "f1_macro": f1_score(true_seqs, pred_seqs, average="macro", zero_division=0),
        "precision_micro": precision_score(true_seqs, pred_seqs, average="micro", zero_division=0),
        "recall_micro": recall_score(true_seqs, pred_seqs, average="micro", zero_division=0),
        "f1_micro": f1_score(true_seqs, pred_seqs, average="micro", zero_division=0),
    }
    text_report = classification_report(true_seqs, pred_seqs, digits=4, zero_division=0)
    dict_report = classification_report(true_seqs, pred_seqs, output_dict=True,
                                        zero_division=0)

    out = Path(EVAL_OUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    (out / "test_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "classification_report.txt").write_text(text_report, encoding="utf-8")
    plot_per_class_metrics(dict_report, str(out / "per_class_metrics.png"))
    plot_confusion_matrix(true_seqs, pred_seqs, labels,
                          str(out / "confusion_matrix.png"))
    plot_summary_table(metrics, str(out / "summary_table.png"))

    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(text_report)


if __name__ == "__main__":
    main()
