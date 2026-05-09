"""Benchmark the fine-tuned NER model on the held-out test split.

Reports ``seqeval`` entity-level metrics (strict BIO matching), which are the
de-facto academic standard for NER:

* Token-level accuracy (sub-word ignored)
* Per-entity-type precision / recall / F1 / support
* Standard micro / macro / weighted averages

Outputs in ``out/evaluation/``:
    classification_report.png   (table chart with all metrics + accuracy row)
    confusion_matrix.png        (token-level BIO confusion, O dropped)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from seqeval.metrics import accuracy_score, classification_report
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
)

from ..core.config import BATCH_SIZE, EVAL_ARTIFACTS_DIR, MODEL_DIR, TEST_PATH
from ..viz.evaluation import plot_classification_report, plot_confusion_matrix
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

    accuracy = accuracy_score(true_seqs, pred_seqs)
    dict_report = classification_report(true_seqs, pred_seqs, output_dict=True, zero_division=0)

    out = Path(EVAL_ARTIFACTS_DIR)
    out.mkdir(parents=True, exist_ok=True)
    plot_classification_report(dict_report, accuracy,
                               str(out / "classification_report.png"))
    plot_confusion_matrix(true_seqs, pred_seqs, labels,
                          str(out / "confusion_matrix.png"))

    print(f"n_test={len(true_seqs)}  token_accuracy={accuracy:.4f}")
    print(classification_report(true_seqs, pred_seqs, digits=4, zero_division=0))


if __name__ == "__main__":
    main()
