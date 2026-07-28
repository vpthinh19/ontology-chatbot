"""Fine-tune PhoBERT to reject questions outside the ontology domain."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .gate_dataset import load_gate_release, validate_gate_release
from .gate_evaluation import evaluate_gate, select_threshold
from .training import _precision_policy
from ..runtime.text import normalize_model_input
from ..settings import ARTIFACTS_DIR, GATE_DIR

PHOBERT_MODEL_ID = "vinai/phobert-base-v2"
PHOBERT_REVISION = "e2375d266bdf39c6e8e9a87af16a5da3190b0cc8"
LABEL_TO_ID = {"out_of_scope": 0, "in_scope": 1}
ID_TO_LABEL = {value: key for key, value in LABEL_TO_ID.items()}
MAX_LENGTH = 128


def _tokenize_batch(tokenizer, batch: dict[str, list]) -> dict[str, list]:
    encoded = tokenizer(
        [normalize_model_input(text) for text in batch["input"]],
        max_length=MAX_LENGTH,
        truncation=True,
    )
    encoded["labels"] = [LABEL_TO_ID[label] for label in batch["label"]]
    return encoded


def _training_argument_values(
    output_dir: Path,
    *,
    precision: dict[str, str | bool],
    smoke_test: bool,
) -> dict[str, object]:
    return {
        "output_dir": str(output_dir / "checkpoints"),
        "num_train_epochs": 5,
        "max_steps": 1 if smoke_test else -1,
        "per_device_train_batch_size": 16,
        "per_device_eval_batch_size": 32,
        "learning_rate": 2e-5,
        "lr_scheduler_type": "cosine",
        "warmup_steps": 0.1,
        "weight_decay": 0.01,
        "optim": "adamw_torch",
        "bf16": precision["bf16"],
        "fp16": precision["fp16"],
        "tf32": precision["tf32"],
        "torch_compile": False,
        "eval_strategy": "no" if smoke_test else "epoch",
        "save_strategy": "no" if smoke_test else "epoch",
        "save_total_limit": 1,
        "save_only_model": True,
        "load_best_model_at_end": not smoke_test,
        "metric_for_best_model": "macro_f1",
        "greater_is_better": True,
        "logging_strategy": "steps",
        "logging_steps": 1 if smoke_test else 25,
        "disable_tqdm": True,
        "report_to": "none",
        "seed": 42,
        "data_seed": 42,
    }


def _softmax_positive(logits, np) -> list[float]:
    values = np.asarray(logits, dtype=np.float64)
    values -= values.max(axis=1, keepdims=True)
    exponentials = np.exp(values)
    return (exponentials[:, 1] / exponentials.sum(axis=1)).tolist()


def _dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train_gate(args: argparse.Namespace) -> dict[str, object]:
    try:
        import numpy as np
        import torch
        import transformers
        from datasets import Dataset
        from huggingface_hub import snapshot_download
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:  # pragma: no cover - CLI requires train extra.
        raise RuntimeError("install the train extra to fine-tune the gate") from exc

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RuntimeError(f"gate output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    release = load_gate_release(args.dataset_dir)
    validation = validate_gate_release(release)
    if not validation["valid"]:
        raise RuntimeError(f"gate dataset is invalid: {validation['errors'][:5]}")
    train_rows = release["train"]
    val_rows = release["val"]
    test_rows = release["test"]
    if args.smoke_test:
        train_rows = _balanced_subset(train_rows, 16)
        val_rows = _balanced_subset(val_rows, 8)

    snapshot = Path(
        snapshot_download(
            PHOBERT_MODEL_ID,
            revision=PHOBERT_REVISION,
            local_files_only=args.local_files_only,
        )
    )
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    cuda_available = torch.cuda.is_available()
    precision = _precision_policy(
        cuda_available=cuda_available,
        bf16_supported=torch.cuda.is_bf16_supported() if cuda_available else False,
        compute_capability=torch.cuda.get_device_capability() if cuda_available else None,
    )
    dtype = getattr(torch, str(precision["dtype"]))
    model = AutoModelForSequenceClassification.from_pretrained(
        snapshot,
        local_files_only=True,
        num_labels=2,
        id2label=ID_TO_LABEL,
        label2id=LABEL_TO_ID,
        dtype=dtype,
    )

    def make_dataset(rows):
        dataset = Dataset.from_dict(
            {
                "input": [row["input"] for row in rows],
                "label": [row["label"] for row in rows],
            }
        )
        return dataset.map(
            lambda batch: _tokenize_batch(tokenizer, batch),
            batched=True,
            remove_columns=["input", "label"],
        )

    train_dataset = make_dataset(train_rows)
    val_dataset = make_dataset(val_rows)
    test_dataset = None if args.smoke_test else make_dataset(test_rows)

    def compute_metrics(prediction) -> dict[str, float]:
        probabilities = _softmax_positive(prediction.predictions, np)
        report = evaluate_gate(
            np.asarray(prediction.label_ids).astype(int).tolist(),
            probabilities,
            0.5,
        )
        return {
            key: float(report[key])
            for key in (
                "accuracy",
                "in_scope_precision",
                "in_scope_recall",
                "in_scope_f1",
                "out_of_scope_recall",
                "false_acceptance_rate",
                "false_rejection_rate",
                "macro_f1",
                "roc_auc",
                "average_precision",
            )
        }

    training_values = _training_argument_values(
        output_dir,
        precision=precision,
        smoke_test=args.smoke_test,
    )
    training_args = TrainingArguments(**training_values)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=DataCollatorWithPadding(tokenizer, pad_to_multiple_of=8),
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
    )
    if cuda_available:
        torch.cuda.reset_peak_memory_stats()
    train_result = trainer.train()
    val_prediction = trainer.predict(val_dataset)
    val_labels = np.asarray(val_prediction.label_ids).astype(int).tolist()
    val_probabilities = _softmax_positive(val_prediction.predictions, np)
    threshold = select_threshold(val_labels, val_probabilities)
    report: dict[str, object] = {
        "validation": evaluate_gate(val_labels, val_probabilities, threshold),
        "training": {
            "model_id": PHOBERT_MODEL_ID,
            "revision": PHOBERT_REVISION,
            "seed": 42,
            "epochs": 5,
            "train_records": len(train_rows),
            "validation_records": len(val_rows),
            "dataset_manifest_sha256": _dataset_sha256(
                Path(args.dataset_dir) / "manifest.json"
            ),
            "batch_size": 16,
            "dynamic_padding_multiple": 8,
            "word_segmentation": False,
            "dtype": precision["dtype"],
            "bf16": precision["bf16"],
            "fp16": precision["fp16"],
            "tf32": precision["tf32"],
            "torch_compile": False,
            "dropout_policy": "checkpoint_default",
            "learning_rate": 2e-5,
            "lr_scheduler_type": "cosine",
            "warmup_steps": 0.1,
            "train_runtime_seconds": train_result.metrics.get("train_runtime", 0.0),
            "train_loss": train_result.metrics.get("train_loss", 0.0),
            "peak_vram_bytes": torch.cuda.max_memory_allocated() if cuda_available else None,
            "best_checkpoint": trainer.state.best_model_checkpoint,
            "smoke_test": args.smoke_test,
            "torch_version": torch.__version__,
            "transformers_version": transformers.__version__,
            "gpu": torch.cuda.get_device_name() if cuda_available else None,
        },
        "training_log": trainer.state.log_history,
    }
    predictions = []
    if test_dataset is not None:
        test_prediction = trainer.predict(test_dataset)
        test_labels = np.asarray(test_prediction.label_ids).astype(int).tolist()
        test_probabilities = _softmax_positive(test_prediction.predictions, np)
        report["test"] = evaluate_gate(test_labels, test_probabilities, threshold)
        predictions = [
            {
                "input": row["input"],
                "label": row["label"],
                "in_scope_probability": probability,
                "accepted": probability >= threshold,
            }
            for row, probability in zip(test_rows, test_probabilities, strict=True)
        ]

    (output_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if predictions:
        (output_dir / "test_predictions.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
            encoding="utf-8",
        )
    if args.save_model:
        model_dir = output_dir / "model"
        trainer.save_model(model_dir)
        tokenizer.save_pretrained(model_dir)
        (output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "model_id": PHOBERT_MODEL_ID,
                    "revision": PHOBERT_REVISION,
                    "threshold": threshold,
                    "label_to_id": LABEL_TO_ID,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _balanced_subset(rows: list[dict[str, str]], per_label: int) -> list[dict[str, str]]:
    selected = []
    for label in LABEL_TO_ID:
        selected.extend(
            [row for row in rows if row["label"] == label][:per_label]
        )
    return selected


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=GATE_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "models" / "phobert-gate",
    )
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    train_gate(_parse_args(argv))
