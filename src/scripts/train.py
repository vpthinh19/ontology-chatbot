"""PhoBERT fine-tuning — BCE vs ASL vs ZLPR.

Trains models on identical data with different loss strategies:
    - BCE (baseline)  — BCEWithLogitsLoss
    - ASL             — asymmetric focusing (Ridnik et al., 2021)
    - ZLPR            — ranking-based, hyperparameter-free (Su et al., 2022)

Outputs:
    - Training/validation curves (loss + mAP + F1-macro)
    - Validation benchmark (2x2 grouped bar + summary table)
    - UMAP of train embeddings: Base vs BCE vs ASL vs ZLPR

Usage:
    python -m src.scripts.train
"""

from __future__ import annotations

import os

from datasets import load_dataset
import numpy as np
import torch
from transformers import (
    AutoModel,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)
import gc

from ..core.config import (
    ASL_CLIP,
    ASL_GAMMA_NEG,
    ASL_GAMMA_POS,
    BATCH_SIZE,
    CHECKPOINT_DIR,
    EPOCHS,
    LABEL_MAP_PATH,
    LEARNING_RATE,
    MAX_LENGTH,
    MODEL_ASL_DIR,
    MODEL_BCE_DIR,
    MODEL_NAME,
    MODEL_ZLPR_DIR,
    RANDOM_SEED,
    TRAIN_DATASET_PATH,
    TRAIN_OUTPUT_DIR,
    VAL_SIZE,
)
from ..utils.labels import build_mlb, load_label_names
from ..utils.preprocessing import preprocess_batch
from ..trainers import AsymmetricTrainer, ZLPRTrainer
from ..utils.inference import extract_embeddings
from ..utils.metrics import compute_metrics, make_compute_metrics_fn
from ..viz import (
    plot_label_distribution,
    plot_metrics_comparison,
    plot_summary_table,
    plot_training_curves,
    plot_umap_comparison,
)


# Training setup

def create_training_arguments(output_dir: str) -> TrainingArguments:
    """Create standard TrainingArguments shared by all models."""
    use_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    use_fp16 = torch.cuda.is_available() and not use_bf16

    return TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        eval_strategy="steps",
        eval_steps=0.1,
        logging_strategy="steps",
        logging_steps=0.1,
        save_strategy="steps",
        save_steps=0.1,
        save_total_limit=2,
        bf16=use_bf16,
        fp16=use_fp16,
        optim="adamw_torch_fused" if torch.cuda.is_available() else "adamw_torch",
        learning_rate=LEARNING_RATE,
        lr_scheduler_type="cosine",
        weight_decay=0.005,
        warmup_steps=0.1,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        seed=RANDOM_SEED,
        dataloader_pin_memory=torch.cuda.is_available(),
    )


def create_classification_model(num_labels: int) -> AutoModelForSequenceClassification:
    """Instantiate a fresh PhoBERT model for sequence classification."""
    return AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=num_labels,
        problem_type="multi_label_classification",
    )


# Pipeline definitions

# (name, model_dir, trainer_cls, trainer_kwargs)
_PIPELINES: list[tuple[str, str, type, dict]] = [
    ("BCE", MODEL_BCE_DIR, Trainer, {}),
    ("ASL", MODEL_ASL_DIR, AsymmetricTrainer, {
        "asl_gamma_pos": ASL_GAMMA_POS,
        "asl_gamma_neg": ASL_GAMMA_NEG,
        "asl_clip": ASL_CLIP,
    }),
    ("ZLPR", MODEL_ZLPR_DIR, ZLPRTrainer, {}),
]


# Main execution

def main() -> None:
    os.makedirs(TRAIN_OUTPUT_DIR, exist_ok=True)
    for _, model_dir, _, _ in _PIPELINES:
        os.makedirs(model_dir, exist_ok=True)

    # Load data
    print("Loading Data...")

    label_names = load_label_names(LABEL_MAP_PATH)
    mlb = build_mlb(label_names)
    num_labels = len(label_names)

    raw_dataset = load_dataset("json", data_files={"train": TRAIN_DATASET_PATH})["train"]
    split_dataset = raw_dataset.train_test_split(test_size=VAL_SIZE, seed=RANDOM_SEED)

    train_dataset = split_dataset["train"]
    val_dataset = split_dataset["test"]

    print(f"  Train : {len(train_dataset)} samples")
    print(f"  Val   : {len(val_dataset)} samples")
    print(f"  Labels: {num_labels}")

    # Dataset visualization
    print("Dataset Visualization...")
    train_labels_raw = train_dataset["labels"]
    val_labels_raw = val_dataset["labels"]

    plot_label_distribution(
        {"Train": train_labels_raw, "Val": val_labels_raw},
        label_names,
        os.path.join(TRAIN_OUTPUT_DIR, "label_distribution.png"),
    )

    # Preprocessing and Tokenization
    print("Preprocessing and Tokenization...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    def process_batch(examples):
        texts = preprocess_batch(examples["text"], word_segmentation=True)
        tokenized = tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=MAX_LENGTH,
        )
        labels_matrix = mlb.transform(examples["labels"])  # type: ignore
        # Convert sparse matrix to dense array
        if hasattr(labels_matrix, 'toarray'):
            labels_array = labels_matrix.toarray()  # type: ignore[attr-defined]
        else:
            labels_array = labels_matrix  # type: ignore
        tokenized["labels"] = labels_array.astype(np.float32).tolist()  # type: ignore[attr-defined]
        return tokenized

    cols_to_remove = train_dataset.column_names
    train_dataset = train_dataset.map(
        process_batch, batched=True, batch_size=1000, remove_columns=cols_to_remove
    )
    val_dataset = val_dataset.map(
        process_batch, batched=True, batch_size=1000, remove_columns=cols_to_remove
    )

    train_dataset.set_format("torch")
    val_dataset.set_format("torch")

    print(f"  Tokenized train: {len(train_dataset)} samples")
    print(f"  Tokenized val  : {len(val_dataset)} samples")

    compute_metrics_fn = make_compute_metrics_fn()

    # Extract Base Embeddings First
    print("Extracting Base Embeddings (UMAP Prep)...")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    base_model = AutoModel.from_pretrained(MODEL_NAME).to(device)
    base_embeddings = extract_embeddings(base_model, train_dataset, batch_size=BATCH_SIZE)
    del base_model
    gc.collect()
    torch.cuda.empty_cache()
    
    embeddings: dict[str, np.ndarray] = {"Base PhoBERT": base_embeddings}
    all_metrics: dict[str, dict[str, float]] = {}
    training_logs: dict[str, list[dict]] = {}

    # Train models
    for name, model_dir, trainer_cls, kwargs in _PIPELINES:
        print(f"Training & Evaluation: {name}...")

        model = create_classification_model(num_labels)
        trainer = trainer_cls(
            model=model,
            args=create_training_arguments(os.path.join(CHECKPOINT_DIR, name.lower())),
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            compute_metrics=compute_metrics_fn,
            callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
            **kwargs,
        )
        
        # Train
        result = trainer.train()
        print(f"  Train Done: {result.metrics}")

        # Save
        trainer.save_model(model_dir)
        tokenizer.save_pretrained(model_dir)
        print(f"  Model saved: {model_dir}")
        
        # Save training logs for curves
        training_logs[name] = trainer.state.log_history

        # Evaluate on validation
        val_out = trainer.predict(val_dataset)
        all_metrics[name] = compute_metrics(val_out.predictions, val_out.label_ids)
        
        # Extract embeddings for UMAP
        print(f"  Extracting {name} fine-tuned embeddings ...")
        embeddings[f"{name} Fine-tuned"] = extract_embeddings(
            model,  # type: ignore
            train_dataset, batch_size=BATCH_SIZE,
        )

        # Clear VRAM
        del model
        del trainer
        del val_out
        gc.collect()
        torch.cuda.empty_cache()


    # Training curves comparison
    print("Plotting Training Curves...")

    plot_training_curves(
        training_logs,
        os.path.join(TRAIN_OUTPUT_DIR, "training_curves.png"),
    )

    # Validation metrics comparison
    print("Computing Validation Metrics...")

    # Print comparison table
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
        os.path.join(TRAIN_OUTPUT_DIR, "val_metrics_comparison.png"),
        title="Validation Benchmark",
    )

    plot_summary_table(
        all_metrics,
        os.path.join(TRAIN_OUTPUT_DIR, "val_summary_table.png"),
        title="Validation Summary",
    )

    # UMAP: Base vs fine-tuned on training data
    print("Plotting UMAP - Train Embeddings...")

    plot_umap_comparison(
        embeddings,
        train_labels_raw, label_names,
        os.path.join(TRAIN_OUTPUT_DIR, "umap_train_comparison.png"),
        suptitle="UMAP -- Train Set Embeddings",
    )

    print(f"\n  All outputs saved to: {TRAIN_OUTPUT_DIR}")
    model_dirs = ", ".join(d for _, d, _, _ in _PIPELINES)
    print(f"  Models saved to: {model_dirs}")
    print("\nDone! Next: python -m src.scripts.evaluate")


if __name__ == "__main__":
    main()
