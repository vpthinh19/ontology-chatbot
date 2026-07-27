"""Fine-tune a supported encoder-decoder model to generate direct SPARQL."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .benchmark import (
    evaluate_benchmark,
    load_benchmark,
    validate_benchmark,
)
from ..settings import ARTIFACTS_DIR, DATASET_DIR
from .dataset import load_release, validate_release
from .evaluation import evaluate_predictions
from ..runtime.text import normalize_model_input
from ..tools.tokenizer import (
    BARTPHO_MODEL_ID,
    BARTPHO_REVISION,
    DEFAULT_VIT5_TOKENIZER_DIR,
    T5GEMMA_MODEL_ID,
    T5GEMMA_REVISION,
    VIT5_MODEL_ID,
    VIT5_REVISION,
    audit_target_roundtrip,
    prepare_vit5_tokenizer,
)
from ..runtime.sparql import load_ontology

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
    "t5gemma2": {
        "model_id": T5GEMMA_MODEL_ID,
        "revision": T5GEMMA_REVISION,
        "batch_size": 8,
        "gradient_accumulation": 1,
        "attention": "sdpa",
        "gradient_checkpointing": True,
    },
}
MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 160


def train(args: argparse.Namespace) -> dict:
    try:
        import numpy as np
        import torch
        import transformers
        from datasets import Dataset
        from huggingface_hub import snapshot_download
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            EarlyStoppingCallback,
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
        tokenizer_kwargs = (
            {"fix_mistral_regex": False} if args.model == "t5gemma2" else {}
        )
        tokenizer = AutoTokenizer.from_pretrained(
            snapshot,
            revision=spec["revision"],
            local_files_only=True,
            trust_remote_code=True,
            **tokenizer_kwargs,
        )

    release = load_release(args.dataset_dir)
    graph = load_ontology()
    dataset_report = validate_release(release, graph)
    rows = release["train"] + release["val"]
    targets = tuple(dict.fromkeys(row["target"] for row in rows))
    audit_target_roundtrip(tokenizer, targets)

    train_rows = release["train"]
    validation_rows = release["val"]
    if args.smoke_test:
        train_rows = _smoke_subset(train_rows, 16)
        validation_rows = _smoke_subset(validation_rows, 8)

    model = AutoModelForSeq2SeqLM.from_pretrained(
        snapshot,
        local_files_only=True,
        attn_implementation=spec["attention"],
        dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    _configure_greedy_generation(model.generation_config)
    if spec.get("gradient_checkpointing", False):
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
    if args.model == "bartpho" and not args.keep_dropout:
        _disable_dropout(model, torch)

    train_dataset = _tokenized_dataset(Dataset, train_rows, tokenizer)
    validation_dataset = _tokenized_dataset(Dataset, validation_rows, tokenizer)
    steps_per_epoch = math.ceil(
        len(train_rows) / (spec["batch_size"] * spec["gradient_accumulation"])
    )
    eval_steps = max(1, round(steps_per_epoch * args.eval_every_epochs))
    short_run = args.smoke_test
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

    keep_checkpoints = args.save_model and not short_run
    effective_max_steps = 1 if args.smoke_test else args.max_steps
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        max_steps=effective_max_steps,
        per_device_train_batch_size=spec["batch_size"],
        per_device_eval_batch_size=spec.get("eval_batch_size", 1),
        gradient_accumulation_steps=spec["gradient_accumulation"],
        learning_rate=args.learning_rate,
        lr_scheduler_type="constant",
        warmup_steps=0,
        weight_decay=0.005,
        optim="adamw_8bit",
        bf16=True,
        tf32=True,
        torch_compile=False,
        gradient_checkpointing=spec.get("gradient_checkpointing", False),
        gradient_checkpointing_kwargs={"use_reentrant": False},
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
        logging_steps=1 if args.smoke_test else 50,
        disable_tqdm=True,
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
        callbacks=(
            [EarlyStoppingCallback(early_stopping_patience=3)]
            if keep_checkpoints
            else None
        ),
    )

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    train_result = trainer.train()
    inference_model = trainer.model
    if trainer.state.best_model_checkpoint:
        # Reload through from_pretrained instead of Trainer's raw state_dict path.
        # Some architectures (notably T5Gemma2) remap checkpoint keys while loading.
        trainer.model = None
        trainer.model_wrapped = None
        del inference_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        inference_model = AutoModelForSeq2SeqLM.from_pretrained(
            trainer.state.best_model_checkpoint,
            local_files_only=True,
            attn_implementation=spec["attention"],
            dtype=torch.bfloat16,
            trust_remote_code=True,
        ).to(training_args.device)
        _configure_greedy_generation(inference_model.generation_config)
    decoded = _generate_rows(
        inference_model,
        tokenizer,
        validation_rows,
        torch,
        batch_size=spec.get("eval_batch_size", 1),
    )
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
        "gradient_checkpointing": spec.get("gradient_checkpointing", False),
        "generation_do_sample": False,
        "dropout_disabled": args.model == "bartpho" and not args.keep_dropout,
        "optimizer": "adamw_8bit",
        "learning_rate": args.learning_rate,
        "evaluation_every_epochs": args.eval_every_epochs,
        "early_stopping_patience": 3 if keep_checkpoints else None,
        "train_runtime_seconds": round(train_result.metrics.get("train_runtime", 0.0), 3),
        "train_loss": round(train_result.metrics.get("train_loss", 0.0), 6),
        "peak_vram_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "smoke_test": args.smoke_test,
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "gpu": torch.cuda.get_device_name() if torch.cuda.is_available() else None,
    }
    report["training_log"] = trainer.state.log_history
    metrics_path = output_dir / "metrics.json"
    metrics_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.save_model:
        inference_model.save_pretrained(output_dir / "model")
        tokenizer.save_pretrained(output_dir / "model")
    if args.benchmark_after_training:
        benchmark_rows = load_benchmark()
        benchmark_validation = validate_benchmark(
            benchmark_rows,
            graph,
            training_rows=rows,
        )
        benchmark_decoded = _generate_rows(
            inference_model,
            tokenizer,
            benchmark_rows,
            torch,
            batch_size=spec.get("eval_batch_size", 1),
        )
        benchmark_predictions = dict(
            zip(
                (row["id"] for row in benchmark_rows),
                benchmark_decoded,
                strict=True,
            )
        )
        benchmark_report = evaluate_benchmark(
            benchmark_rows,
            benchmark_predictions,
            graph,
            include_cases=True,
        )
        benchmark_report["benchmark"] = benchmark_validation
        (output_dir / "benchmark_metrics.json").write_text(
            json.dumps(benchmark_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "benchmark_predictions.jsonl").write_text(
            "".join(
                json.dumps(
                    {"id": row["id"], "prediction": prediction},
                    ensure_ascii=False,
                )
                + "\n"
                for row, prediction in zip(
                    benchmark_rows,
                    benchmark_decoded,
                    strict=True,
                )
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {"benchmark_overall": benchmark_report["overall"]},
                ensure_ascii=False,
                indent=2,
            )
        )
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
        labels = tokenizer(
            text_target=batch["target"],
            max_length=MAX_TARGET_LENGTH,
            truncation=True,
        )["input_ids"]
        encoded["labels"] = [
            _ensure_eos_token(ids, tokenizer.eos_token_id, MAX_TARGET_LENGTH)
            for ids in labels
        ]
        return encoded

    return dataset.map(tokenize, batched=True, remove_columns=["source", "target"])


def _ensure_eos_token(
    ids: list[int], eos_token_id: int | None, max_length: int
) -> list[int]:
    """Terminate target labels even when a tokenizer only inserts BOS."""

    if eos_token_id is None:
        raise ValueError("a seq2seq target tokenizer must define eos_token_id")
    output = list(ids)
    if output and output[-1] == eos_token_id:
        return output
    if len(output) >= max_length:
        output[-1] = eos_token_id
    else:
        output.append(eos_token_id)
    return output


def _configure_greedy_generation(config) -> None:
    """Remove inherited sampling settings from structured generation."""

    config.do_sample = False
    config.top_p = None
    config.top_k = None


def _generate_rows(model, tokenizer, rows, torch, *, batch_size: int) -> list[str]:
    """Generate from a normally reloaded checkpoint, independent of Trainer state."""

    model.eval()
    use_cache = model.config.use_cache
    model.config.use_cache = True
    predictions = []
    try:
        with torch.inference_mode():
            for offset in range(0, len(rows), batch_size):
                batch = rows[offset : offset + batch_size]
                encoded = tokenizer(
                    [normalize_model_input(row["input"]) for row in batch],
                    max_length=MAX_SOURCE_LENGTH,
                    truncation=True,
                    padding=True,
                    pad_to_multiple_of=8,
                    return_tensors="pt",
                ).to(model.device)
                output = model.generate(
                    **encoded,
                    max_length=MAX_TARGET_LENGTH,
                    num_beams=1,
                    do_sample=False,
                )
                predictions.extend(
                    text.strip()
                    for text in tokenizer.batch_decode(output, skip_special_tokens=True)
                )
    finally:
        model.config.use_cache = use_cache
    return predictions


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
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR / "sparql_training")
    parser.add_argument("--epochs", type=float, default=60.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--eval-every-epochs", type=float, default=5.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--keep-dropout", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--benchmark-after-training", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()
    if args.benchmark_after_training and not args.save_model:
        parser.error("--benchmark-after-training requires --save-model")
    if args.benchmark_after_training and args.smoke_test:
        parser.error("benchmark is only available after a full training run")
    return args


def main() -> None:
    train(_parse_args())


if __name__ == "__main__":
    main()
