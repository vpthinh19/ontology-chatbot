"""Benchmark fine-tuned PhoBERT NER vs an untrained baseline on the held-out test split.

Two evaluations are run by default:

* ``finetuned`` — checkpoint at :data:`MODEL_DIR` (encoder + head both trained).
* ``baseline``  — :data:`MODEL_NAME` (``vinai/phobert-base-v2``) with a random-
  initialised classification head. Encoder is the public Vietnamese-pretrained
  PhoBERT v2; the head has *never* seen a BIO label. This isolates the
  contribution of supervised fine-tuning by holding every other component
  (tokenizer, encoder pretraining, dataset, BIO scheme) constant.

Reports use ``seqeval`` entity-level metrics — the de-facto academic standard
for NER (strict BIO matching), plus token-level accuracy.

Outputs in ``artifacts/evaluation/``::

    finetuned/classification_report.png   per-entity precision/recall/F1
    finetuned/confusion_matrix.png        token-level BIO confusion (O dropped)
    baseline/classification_report.png
    baseline/confusion_matrix.png
    comparison.png                        grouped bars: accuracy + macro P/R/F1
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch
from seqeval.metrics import accuracy_score, classification_report
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    set_seed,
)

from ..config import (
    BATCH_SIZE,
    EVAL_ARTIFACTS_DIR,
    MODEL_DIR,
    MODEL_NAME,
    SEED,
    TEST_PATH,
)
from ..ner_model import NerModel
from ..viz.evaluation import (
    plot_classification_report,
    plot_comparison,
    plot_confusion_matrix,
)


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


def _load_finetuned():
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR), use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(str(MODEL_DIR))
    return model, tokenizer


def _load_baseline(labels: list[str], l2i: dict[str, int], i2l: dict[int, str]):
    # Seed BEFORE from_pretrained: the new Linear(hidden, n_labels) head is
    # init'd from torch's global RNG, so fixing the seed makes baseline scores
    # reproducible across runs (otherwise F1 jitters by a few points).
    set_seed(SEED)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(labels),
        id2label=i2l,
        label2id=l2i,
    )
    return model, tokenizer


def _eval_one(
    model,
    tokenizer,
    labels: list[str],
    l2i: dict[str, int],
    i2l: dict[int, str],
    name: str,
    out_dir: Path,
) -> tuple[float, dict]:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device).eval()

    ds = NerModel.load_split(TEST_PATH, l2i).map(
        NerModel.make_tokenize_fn(tokenizer),
        batched=True, remove_columns=["tokens", "tags"]
    )
    loader = DataLoader(ds, batch_size=BATCH_SIZE,
                        collate_fn=DataCollatorForTokenClassification(tokenizer))

    true_seqs, pred_seqs = _predict(model, loader, device, i2l)

    accuracy = accuracy_score(true_seqs, pred_seqs)
    dict_report = classification_report(true_seqs, pred_seqs, output_dict=True, zero_division=0)

    out_dir.mkdir(parents=True, exist_ok=True)
    title = f"PhoBERT NER ({name}) — Classification Report"
    plot_classification_report(dict_report, accuracy,
                               str(out_dir / "classification_report.png"),
                               title=title)
    plot_confusion_matrix(true_seqs, pred_seqs, labels,
                          str(out_dir / "confusion_matrix.png"))

    print(f"[{name}] n_test={len(true_seqs)}  token_accuracy={accuracy:.4f}")
    print(classification_report(true_seqs, pred_seqs, digits=4, zero_division=0))
    return accuracy, dict_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--target",
        choices=["finetuned", "baseline", "both"],
        default="both",
        help="Which evaluation(s) to run. 'both' (default) also writes comparison.png.",
    )
    args = parser.parse_args()

    labels, l2i, i2l = NerModel.label_mappings()
    out_root = Path(EVAL_ARTIFACTS_DIR)
    results: dict[str, tuple[float, dict]] = {}

    if args.target in ("finetuned", "both"):
        model, tokenizer = _load_finetuned()
        results["finetuned"] = _eval_one(
            model, tokenizer, labels, l2i, i2l,
            "finetuned", out_root / "finetuned",
        )
        # Free the model before loading the next one — keeps peak RAM at one
        # model's worth (~520MB for PhoBERT-base) rather than two.
        del model, tokenizer

    if args.target in ("baseline", "both"):
        model, tokenizer = _load_baseline(labels, l2i, i2l)
        results["baseline"] = _eval_one(
            model, tokenizer, labels, l2i, i2l,
            "baseline", out_root / "baseline",
        )
        del model, tokenizer

    if len(results) == 2:
        plot_comparison(results, str(out_root / "comparison.png"))


if __name__ == "__main__":
    main()
