"""Benchmark the fine-tuned NER model on the held-out test split.

Reports academic-standard NER metrics computed by ``seqeval`` (entity-level,
strict BIO matching):

- Token-level accuracy (sub-word ignored)
- Entity-level precision / recall / F1, both macro- and micro-averaged
- Per-entity-type precision / recall / F1 / support (classification report)

Outputs:
    out/evaluation/test_metrics.json
    out/evaluation/classification_report.txt
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
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
)
from torch.utils.data import DataLoader

from ..config import BATCH_SIZE, EVAL_OUT_DIR, MODEL_DIR, TEST_PATH
from .dataset import label_mappings, load_split, make_tokenize_fn


def main() -> None:
    _, l2i, i2l = label_mappings()
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    ds = load_split(TEST_PATH, l2i)
    tok_ds = ds.map(make_tokenize_fn(tokenizer), batched=True, remove_columns=ds.column_names)
    collator = DataCollatorForTokenClassification(tokenizer)
    loader = DataLoader(tok_ds, batch_size=BATCH_SIZE * 2, collate_fn=collator)

    true_seqs: list[list[str]] = []
    pred_seqs: list[list[str]] = []
    with torch.no_grad():
        for batch in loader:
            labels = batch.pop("labels")
            batch = {k: v.to(device) for k, v in batch.items()}
            logits = model(**batch).logits.cpu().numpy()
            preds = np.argmax(logits, axis=-1)
            for p_row, l_row in zip(preds, labels.numpy()):
                t_s, p_s = [], []
                for p, l in zip(p_row, l_row):
                    if l == -100:
                        continue
                    t_s.append(i2l[int(l)])
                    p_s.append(i2l[int(p)])
                true_seqs.append(t_s)
                pred_seqs.append(p_s)

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
    report = classification_report(true_seqs, pred_seqs, digits=4, zero_division=0)

    out_dir = Path(EVAL_OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "test_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "classification_report.txt").write_text(report, encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    print(report)


if __name__ == "__main__":
    main()
