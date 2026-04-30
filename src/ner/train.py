"""Fine-tune PhoBERT for token-level NER on the synthetic academic-procedure corpus.

Outputs:
    - models/phobert-ner/        (best model, tokenizer, label maps)
    - out/training/log_history.json
    - out/training/training_curves.png  (train loss / val loss / val accuracy / val F1-macro)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from seqeval.metrics import accuracy_score, f1_score, precision_score, recall_score
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
    set_seed,
)

from ..config import (
    BATCH_SIZE,
    EPOCHS,
    LEARNING_RATE,
    MODEL_DIR,
    MODEL_NAME,
    SEED,
    TRAIN_OUT_DIR,
    TRAIN_PATH,
    VAL_SIZE,
    WARMUP_RATIO,
    WEIGHT_DECAY,
)
from ..viz.training_curves import plot_training_curves
from .dataset import label_mappings, load_split, make_tokenize_fn


def _build_compute_metrics(i2l: dict[int, str]):
    def _compute(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        true_seqs, pred_seqs = [], []
        for p_row, l_row in zip(preds, labels):
            t_seq, p_seq = [], []
            for p, l in zip(p_row, l_row):
                if l == -100:
                    continue
                t_seq.append(i2l[int(l)])
                p_seq.append(i2l[int(p)])
            true_seqs.append(t_seq)
            pred_seqs.append(p_seq)
        return {
            "accuracy": accuracy_score(true_seqs, pred_seqs),
            "precision_macro": precision_score(true_seqs, pred_seqs, average="macro", zero_division=0),
            "recall_macro": recall_score(true_seqs, pred_seqs, average="macro", zero_division=0),
            "f1_macro": f1_score(true_seqs, pred_seqs, average="macro", zero_division=0),
            "f1_micro": f1_score(true_seqs, pred_seqs, average="micro", zero_division=0),
        }

    return _compute


def main() -> None:
    set_seed(SEED)
    labels, l2i, i2l = label_mappings()

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    full = load_split(TRAIN_PATH, l2i)
    split = full.train_test_split(test_size=VAL_SIZE, seed=SEED)
    tok_fn = make_tokenize_fn(tokenizer)
    train_ds = split["train"].map(tok_fn, batched=True, remove_columns=split["train"].column_names)
    val_ds = split["test"].map(tok_fn, batched=True, remove_columns=split["test"].column_names)

    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME, num_labels=len(labels), id2label=i2l, label2id=l2i,
    )

    args = TrainingArguments(
        output_dir=str(MODEL_DIR),
        overwrite_output_dir=True,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE * 2,
        learning_rate=LEARNING_RATE,
        weight_decay=WEIGHT_DECAY,
        warmup_ratio=WARMUP_RATIO,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_strategy="epoch",
        report_to="none",
        seed=SEED,
        fp16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=_build_compute_metrics(i2l),
    )
    trainer.train()
    trainer.save_model(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    out_dir = Path(TRAIN_OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "log_history.json"
    log_path.write_text(json.dumps(trainer.state.log_history, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    plot_training_curves({"PhoBERT-NER": trainer.state.log_history},
                         str(out_dir / "training_curves.png"))


if __name__ == "__main__":
    main()
