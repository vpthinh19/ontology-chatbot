"""Fine-tune BARTpho or ViT5 to generate direct SPARQL."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ..config import ARTIFACTS_DIR, DATASET_PATH
from ..dataset import load_dataset, validate_dataset
from ..evaluation import evaluate_predictions
from ..model_text import normalize_model_input
from ..model_tokenizers import (
    BARTPHO_MODEL_ID,
    BARTPHO_REVISION,
    DEFAULT_VIT5_TOKENIZER_DIR,
    VIT5_MODEL_ID,
    VIT5_REVISION,
    audit_target_roundtrip,
    prepare_vit5_tokenizer,
)
from ..query_engine import load_ontology

MODEL_SPECS = {
    "bartpho": {
        "model_id": BARTPHO_MODEL_ID,
        "revision": BARTPHO_REVISION,
        "batch_size": 4,
        "gradient_accumulation": 2,
        "attention": "sdpa",
    },
    "vit5": {
        "model_id": VIT5_MODEL_ID,
        "revision": VIT5_REVISION,
        "batch_size": 8,
        "gradient_accumulation": 1,
        "attention": "eager",
    },
}
MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 160


def train(args: argparse.Namespace) -> dict:
    try:
        import numpy as np
        import torch
        from datasets import Dataset
        from huggingface_hub import snapshot_download
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
        )
    except ImportError as exc:  # pragma: no cover - CLI requires train extra.
        raise RuntimeError("install the train extra to fine-tune models") from exc

    spec = MODEL_SPECS[args.model]
    snapshot = Path(
        snapshot_download(
            spec["model_id"],
            revision=spec["revision"],
            local_files_only=args.local_files_only,
        )
    )
    if args.model == "vit5":
        if not (DEFAULT_VIT5_TOKENIZER_DIR / "manifest.json").is_file():
            prepare_vit5_tokenizer(snapshot, DEFAULT_VIT5_TOKENIZER_DIR)
        tokenizer = AutoTokenizer.from_pretrained(
            DEFAULT_VIT5_TOKENIZER_DIR,
            local_files_only=True,
        )
    else:
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot,
            revision=spec["revision"],
            local_files_only=True,
            trust_remote_code=True,
        )

    rows = load_dataset(args.dataset)
    graph = load_ontology()
    dataset_report = validate_dataset(rows, graph)
    targets = tuple(dict.fromkeys(row["target"] for row in rows))
    audit_target_roundtrip(tokenizer, targets)

    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    if args.learning_audit:
        train_rows = _learning_audit_subset(train_rows, 16)
        validation_rows = list(train_rows)
    elif args.smoke_test:
        train_rows = _smoke_subset(train_rows, 16)
        validation_rows = _smoke_subset(validation_rows, 8)

    model = AutoModelForSeq2SeqLM.from_pretrained(
        snapshot,
        local_files_only=True,
        attn_implementation=spec["attention"],
        dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    if args.model == "bartpho" and not args.keep_dropout:
        _disable_dropout(model, torch)

    train_dataset = _tokenized_dataset(Dataset, train_rows, tokenizer)
    validation_dataset = _tokenized_dataset(Dataset, validation_rows, tokenizer)
    steps_per_epoch = math.ceil(
        len(train_rows) / (spec["batch_size"] * spec["gradient_accumulation"])
    )
    eval_steps = max(1, round(steps_per_epoch * args.eval_every_epochs))
    output_dir = Path(args.output_dir) / args.model
    output_dir.mkdir(parents=True, exist_ok=True)

    def compute_metrics(prediction) -> dict[str, float]:
        prediction_ids = prediction.predictions
        if isinstance(prediction_ids, tuple):
            prediction_ids = prediction_ids[0]
        prediction_ids = np.asarray(prediction_ids).copy()
        prediction_ids[prediction_ids < 0] = tokenizer.pad_token_id
        decoded = [text.strip() for text in tokenizer.batch_decode(prediction_ids, skip_special_tokens=True)]
        report = evaluate_predictions(validation_rows, decoded, graph)
        return {
            "parse_rate": report["overall"]["parse_rate"],
            "execution_rate": report["overall"]["execution_rate"],
            "answer_exact_rate": report["overall"]["answer_exact_rate"],
            "canonical_query_exact_rate": report["overall"]["canonical_query_exact_rate"],
        }

    short_run = args.smoke_test or args.learning_audit
    keep_checkpoints = args.save_model and not short_run
    effective_max_steps = 1 if args.smoke_test else args.max_steps
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        max_steps=effective_max_steps,
        per_device_train_batch_size=spec["batch_size"],
        per_device_eval_batch_size=1 if args.smoke_test else spec["batch_size"],
        gradient_accumulation_steps=spec["gradient_accumulation"],
        learning_rate=args.learning_rate,
        lr_scheduler_type="constant",
        warmup_steps=0,
        weight_decay=0.005,
        optim="adamw_8bit",
        bf16=True,
        tf32=True,
        torch_compile=False,
        eval_strategy="no" if short_run else "steps",
        eval_steps=eval_steps,
        save_strategy="steps" if keep_checkpoints else "no",
        save_steps=eval_steps,
        save_total_limit=1 if keep_checkpoints else None,
        save_only_model=True,
        load_best_model_at_end=keep_checkpoints,
        metric_for_best_model="answer_exact_rate",
        greater_is_better=True,
        logging_strategy="steps",
        logging_steps=50 if args.learning_audit else (1 if args.smoke_test else 50),
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        predict_with_generate=True,
        generation_max_length=MAX_TARGET_LENGTH,
        generation_num_beams=1,
    )
    collator = DataCollatorForSeq2Seq(
        tokenizer,
        model=model,
        pad_to_multiple_of=8,
        label_pad_token_id=-100,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=collator,
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
    )

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    train_result = trainer.train()
    trainer.args.per_device_eval_batch_size = 1
    prediction = trainer.predict(
        validation_dataset,
        max_length=MAX_TARGET_LENGTH,
        num_beams=1,
    )
    prediction_ids = prediction.predictions[0] if isinstance(prediction.predictions, tuple) else prediction.predictions
    prediction_ids = np.asarray(prediction_ids).copy()
    prediction_ids[prediction_ids < 0] = tokenizer.pad_token_id
    decoded = [text.strip() for text in tokenizer.batch_decode(prediction_ids, skip_special_tokens=True)]
    report = evaluate_predictions(validation_rows, decoded, graph, include_cases=True)
    report["training"] = {
        "model": args.model,
        "model_id": spec["model_id"],
        "revision": spec["revision"],
        "seed": args.seed,
        "epochs": args.epochs,
        "max_steps": effective_max_steps,
        "train_records": len(train_rows),
        "validation_records": len(validation_rows),
        "dataset_records": dataset_report["records"],
        "batch_size": spec["batch_size"],
        "gradient_accumulation": spec["gradient_accumulation"],
        "dynamic_padding_multiple": 8,
        "bf16": True,
        "tf32": True,
        "torch_compile": False,
        "dropout_disabled": args.model == "bartpho" and not args.keep_dropout,
        "train_runtime_seconds": round(train_result.metrics.get("train_runtime", 0.0), 3),
        "train_loss": round(train_result.metrics.get("train_loss", 0.0), 6),
        "peak_vram_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "smoke_test": args.smoke_test,
        "learning_audit": args.learning_audit,
    }
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.save_model:
        trainer.save_model(str(output_dir / "model"))
        tokenizer.save_pretrained(output_dir / "model")
    print(json.dumps({"overall": report["overall"], "training": report["training"], "metrics": str(metrics_path)}, ensure_ascii=False, indent=2))
    return report


def _tokenized_dataset(Dataset, rows, tokenizer):
    dataset = Dataset.from_dict(
        {
            "source": [normalize_model_input(row["input"]) for row in rows],
            "target": [row["target"] for row in rows],
        }
    )

    def tokenize(batch):
        encoded = tokenizer(
            batch["source"],
            max_length=MAX_SOURCE_LENGTH,
            truncation=True,
        )
        encoded["labels"] = tokenizer(
            text_target=batch["target"],
            max_length=MAX_TARGET_LENGTH,
            truncation=True,
        )["input_ids"]
        return encoded

    return dataset.map(tokenize, batched=True, remove_columns=["source", "target"])


def _smoke_subset(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    selected = []
    seen_targets = set()
    for row in sorted(rows, key=lambda item: len(item["target"]), reverse=True):
        if row["target"] in seen_targets:
            continue
        selected.append(row)
        seen_targets.add(row["target"])
        if len(selected) == limit:
            break
    return selected


def _learning_audit_subset(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    """Select distinct targets with direct, graph, multi-column and aggregate shapes."""

    priorities = (
        lambda target: "COUNT" in target and "FILTER" in target,
        lambda target: "COUNT" in target,
        lambda target: target.startswith("SELECT ?content ?condition ?document"),
        lambda target: target.startswith("SELECT ?condition ?document ?office"),
        lambda target: target.startswith("SELECT ?document ?url"),
        lambda target: ":handledBy" in target and ":email" in target,
        lambda target: ":handledBy" in target and "rdfs:label" in target,
        lambda target: ":condition ?answer" in target,
        lambda target: ":outcome ?answer" in target,
        lambda target: ":content ?answer" in target,
    )
    by_target = {}
    for row in rows:
        by_target.setdefault(row["target"], row)

    selected = []
    seen = set()
    for predicate in priorities:
        for target, row in by_target.items():
            if target not in seen and predicate(target):
                selected.append(row)
                seen.add(target)
                break
    for target, row in sorted(by_target.items(), key=lambda item: len(item[0]), reverse=True):
        if len(selected) == limit:
            break
        if target not in seen:
            selected.append(row)
            seen.add(target)
    return selected


def _disable_dropout(model, torch) -> None:
    for module in model.modules():
        if isinstance(module, torch.nn.Dropout):
            module.p = 0.0
        for attribute in ("dropout", "attention_dropout", "activation_dropout"):
            if isinstance(getattr(module, attribute, None), float):
                setattr(module, attribute, 0.0)
    for attribute in ("dropout", "attention_dropout", "activation_dropout"):
        if hasattr(model.config, attribute):
            setattr(model.config, attribute, 0.0)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR / "sparql_training")
    parser.add_argument("--epochs", type=float, default=60.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--eval-every-epochs", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--keep-dropout", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--learning-audit", action="store_true")
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    if args.smoke_test and args.learning_audit:
        parser.error("--smoke-test and --learning-audit are mutually exclusive")
    if args.learning_audit and args.max_steps < 1:
        parser.error("--learning-audit requires a positive --max-steps")
    return args


def main() -> None:
    train(_parse_args())


if __name__ == "__main__":
    main()
