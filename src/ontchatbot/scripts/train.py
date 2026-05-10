"""Fine-tune PhoBERT for token-level NER on the academic-procedure corpus.

Outputs:
    - ``models/phobert_ner_ft/``                best checkpoint, tokenizer, label maps
    - ``artifacts/training/log_history.json``
    - ``artifacts/training/training_curves.png``  train loss / val loss / accuracy / F1-macro
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
    EarlyStoppingCallback,
    set_seed,
)

from ..config import (
    BATCH_SIZE,
    EPOCHS,
    LEARNING_RATE,
    MODEL_DIR,
    MODEL_NAME,
    SEED,
    TRAIN_ARTIFACTS_DIR,
    TRAIN_PATH,
    VAL_SIZE,
)
from ..ner_model import NerModel
from ..viz.training_curves import plot_training_curves


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
    labels, l2i, i2l = NerModel.label_mappings()

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    full = NerModel.load_split(TRAIN_PATH, l2i)
    split = full.train_test_split(test_size=VAL_SIZE, seed=SEED)
    tok_fn = NerModel.make_tokenize_fn(tokenizer)
    train_ds = split["train"].map(tok_fn, batched=True, remove_columns=split["train"].column_names)
    val_ds = split["test"].map(tok_fn, batched=True, remove_columns=split["test"].column_names)

    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME, num_labels=len(labels), id2label=i2l, label2id=l2i,
    )

    args = TrainingArguments(
        output_dir=str(MODEL_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        optim="adamw_torch_fused" if torch.cuda.is_available() else "adamw_torch",
        learning_rate=LEARNING_RATE,
        weight_decay=0.005,
        warmup_steps=0.1,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=50,
        logging_strategy="steps",
        logging_steps=50,
        report_to="none",
        save_total_limit=1,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        seed=SEED,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=_build_compute_metrics(i2l),
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )
    trainer.train()
    trainer.save_model(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    ARTIFACTS_DIR = Path(TRAIN_ARTIFACTS_DIR)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "log_history.json").write_text(
        json.dumps(trainer.state.log_history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    plot_training_curves(trainer.state.log_history, str(ARTIFACTS_DIR / "training_curves.png"))


if __name__ == "__main__":
    main()
