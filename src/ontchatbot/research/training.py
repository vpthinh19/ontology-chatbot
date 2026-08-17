"""Fine-tune a supported encoder-decoder model to generate direct SPARQL."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ..settings import ARTIFACTS_DIR, DATASET_DIR
from .dataset import load_release
from .evaluation import evaluate_predictions
from .reporting import build_dataset_report, sha256_file
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
    unrepresentable_targets,
)
from ..runtime.sparql import load_ontology

#: Ba model dùng cùng một giao thức lô để benchmark so sánh trong cùng điều kiện.
#:
#: ``eval_batch_size`` phải khai tường minh: mặc định của thư viện là 1, và với
#: ``predict_with_generate`` thì mỗi lần đánh giá sinh tuần tự từng câu.
#:
#: Bộ nhớ trống lúc đầu lượt chạy không phản ánh bộ nhớ tại thời điểm đánh giá:
#: khâu huấn luyện còn giữ chỗ, và đánh giá cần thêm logits
#: ``lô × độ dài đích × cỡ từ điển``.
#:
#: Khi hạ ``batch_size`` vật lý, tăng tích luỹ gradient để giữ nguyên lô hiệu
#: dụng. Bộ nhớ logits tăng theo ``lô × độ dài × từ điển``.
#:
#: ``gradient_checkpointing`` tính lại activation thay vì giữ; nó không đụng tới
#: phép tính, chỉ chậm hơn khoảng một phần tư.
#:
#: Hai giới hạn của thư viện: ``group_by_length`` không còn trong transformers
#: 5.x, và FlashAttention-2 chưa hỗ trợ t5gemma2.
MODEL_SPECS = {
    "bartpho": {
        "model_id": BARTPHO_MODEL_ID,
        "revision": BARTPHO_REVISION,
        "batch_size": 8,
        "eval_batch_size": 6,
        "gradient_accumulation": 1,
        "attention": "sdpa",
        "gradient_checkpointing": False,
            # Từ điển không đánh vần nổi mọi đích, nên trần của model này thấp
        # hơn 100% trước khi học. Đo xem nó đạt tới đâu, đừng từ chối đo.
        "allow_lossy_targets": True,
},
    "vit5": {
        "model_id": VIT5_MODEL_ID,
        "revision": VIT5_REVISION,
        "batch_size": 8,
        "eval_batch_size": 6,
        "gradient_accumulation": 1,
        "attention": "eager",
        "gradient_checkpointing": False,
            # Từ điển không đánh vần nổi mọi đích, nên trần của model này thấp
        # hơn 100% trước khi học. Đo xem nó đạt tới đâu, đừng từ chối đo.
        "allow_lossy_targets": True,
},
    "t5gemma2": {
        "model_id": T5GEMMA_MODEL_ID,
        "revision": T5GEMMA_REVISION,
        "batch_size": 8,
        "eval_batch_size": 6,
        "gradient_accumulation": 1,
        "attention": "sdpa",
        "gradient_checkpointing": False,
    },
}
#: Cấu hình đã chốt bằng đo đạc, nên nó là hằng số chứ không phải tham số: một
#: cờ cho một quyết định đã chốt chỉ là cách để vô tình chạy cấu hình chưa ai đo.
#:
#: ``reduce-overhead`` thay vì ``max-autotune`` vì phần tự dò GEMM của
#: ``max-autotune`` cần nhiều SM hơn cả card huấn luyện lẫn card thử nghiệm có,
#: nên nó chỉ thêm thời gian biên dịch mà không đổi lại được gì.
COMPILE_MODE = "reduce-overhead"
#: Đánh giá mỗi epoch. Nhịp thưa hơn số epoch của một lượt chạy nghĩa là không
#: có mốc nào giữa chừng, và việc chọn checkpoint mất hết ý nghĩa.
EVAL_EVERY_EPOCHS = 1.0
MAX_SOURCE_LENGTH = 128
#: Đây là trần cắt, không phải độ dài đệm. Đích vượt trần bị cắt giữa chừng và
#: không còn canonical; 320 token chừa chỗ cho EOS ngoài đích ViT5 dài nhất.
#:
#: Sau mỗi lần gộp họ truy vấn, phải đo lại độ dài đích trên cả ba tokenizer.
MAX_TARGET_LENGTH = 320
LORA_R = 32
LORA_ALPHA = 64
LORA_DROPOUT = 0.0
_LORA_TARGET_SPECS = {
    "bartpho": {
        "prefixes": ("model.encoder.layers.", "model.decoder.layers."),
        "leaves": frozenset(
            {"q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2"}
        ),
    },
    "vit5": {
        "prefixes": ("encoder.block.", "decoder.block."),
        "leaves": frozenset({"q", "k", "v", "o", "wi", "wo"}),
    },
    "t5gemma2": {
        "prefixes": (
            "model.encoder.text_model.layers.",
            "model.decoder.layers.",
        ),
        "leaves": frozenset(
            {
                "q_proj",
                "k_proj",
                "v_proj",
                "o_proj",
                "gate_proj",
                "up_proj",
                "down_proj",
            }
        ),
    },
}


def _lora_target_modules(model, model_name: str) -> list[str]:
    """Return equivalent attention/FFN modules for a supported seq2seq model."""

    target_spec = _LORA_TARGET_SPECS[model_name]
    targets = [
        name
        for name, _ in model.named_modules()
        if name.startswith(target_spec["prefixes"])
        and name.rsplit(".", 1)[-1] in target_spec["leaves"]
    ]
    if not targets:
        raise RuntimeError("model does not expose compatible text encoder/decoder modules")
    return targets


def _attach_lora_model(
    model,
    *,
    model_name: str,
    LoraConfig,
    TaskType,
    get_peft_model,
):
    """Freeze the base model and attach the locked seq2seq LoRA adapter."""

    config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        target_modules=_lora_target_modules(model, model_name),
    )
    return get_peft_model(model, config)


def _stable_gradient_buffers(TrainerCallback, torch):
    """Callback giữ bộ đệm ``.grad`` cố định qua các bước.

    CUDA graph ghi nhớ địa chỉ của mọi tensor nó chạm tới. PyTorch mặc định đặt
    ``.grad`` về ``None`` sau mỗi bước, nên bước sau cấp tensor ở địa chỉ khác
    và graph đọc phải vùng nhớ đã bị ghi đè. Cấp sẵn bộ đệm rồi chỉ ghi số 0 vào
    chúng thì địa chỉ giữ nguyên, nhờ đó tích luỹ gradient dùng chung được với
    CUDA graphs.
    """

    class _Callback(TrainerCallback):
        def on_train_begin(self, args, state, control, model=None, optimizer=None, **kwargs):
            if optimizer is None or model is None:
                return control
            for parameter in model.parameters():
                if parameter.requires_grad and parameter.grad is None:
                    parameter.grad = torch.zeros_like(parameter)
            original = optimizer.zero_grad

            def zero_grad_in_place(set_to_none: bool = True) -> None:
                original(set_to_none=False)

            optimizer.zero_grad = zero_grad_in_place
            return control

    return _Callback()


def _prepare_output_directory(path: Path) -> None:
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise RuntimeError(f"model output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def train(args: argparse.Namespace) -> dict:
    try:
        import numpy as np
        import torch
        import transformers
        from datasets import Dataset
        from huggingface_hub import snapshot_download
        from peft import (
            LoraConfig,
            PeftModel,
            TaskType,
            get_peft_model,
        )
        from transformers import (
            AutoModelForSeq2SeqLM,
            AutoTokenizer,
            DataCollatorForSeq2Seq,
            EarlyStoppingCallback,
            TrainerCallback,
            Seq2SeqTrainer,
            Seq2SeqTrainingArguments,
        )
    except ImportError as exc:  # pragma: no cover - CLI requires train extra.
        raise RuntimeError("install the train extra to fine-tune models") from exc

    spec = dict(MODEL_SPECS[args.model])
    if args.batch_size:
        effective = spec["batch_size"] * spec["gradient_accumulation"]
        spec["batch_size"] = args.batch_size
        # Giữ nguyên lô hiệu dụng khi thay đổi lô vật lý.
        spec["gradient_accumulation"] = max(1, effective // args.batch_size)
        spec["eval_batch_size"] = min(spec.get("eval_batch_size", 1), args.batch_size)
    # Tính một lần để model, TrainingArguments và metrics dùng cùng một giá trị.
    checkpoint_gradients = _should_checkpoint_gradients(
        spec.get("gradient_checkpointing", False)
    )
    output_dir = Path(args.output_dir) / args.model
    _prepare_output_directory(output_dir)
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
    dataset_report = build_dataset_report(
        release,
        graph,
        dataset_dir=args.dataset_dir,
    )
    _require_training_ready(
        dataset_report["training_readiness"],
        smoke_test=args.smoke_test,
    )
    rows = release["train"] + release["val"]
    targets = tuple(dict.fromkeys(row["target"] for row in rows))
    audit = audit_target_roundtrip(
        tokenizer, targets, strict=not spec.get("allow_lossy_targets", False)
    )
    lossy = unrepresentable_targets(audit)
    if lossy:
        print(
            f"CẢNH BÁO: tokenizer không tái tạo được {len(lossy)}/{len(targets)} đích "
            f"({len(lossy) / len(targets):.1%}). Model KHÔNG THỂ sinh đúng chúng, "
            "nên mọi con số của lượt này phải nêu kèm giới hạn đó."
        )

    train_rows = release["train"]
    validation_rows = release["val"]
    if args.smoke_test:
        train_rows = _smoke_subset(train_rows, 16)
        validation_rows = _smoke_subset(validation_rows, 8)

    cuda_available = torch.cuda.is_available()
    precision = _precision_policy(
        cuda_available=cuda_available,
        bf16_supported=torch.cuda.is_bf16_supported() if cuda_available else False,
        compute_capability=(
            torch.cuda.get_device_capability() if cuda_available else None
        ),
    )
    model_dtype = getattr(torch, str(precision["dtype"]))
    model = AutoModelForSeq2SeqLM.from_pretrained(
        snapshot,
        local_files_only=True,
        attn_implementation=spec["attention"],
        dtype=model_dtype,
    )
    base_parameter_count = sum(parameter.numel() for parameter in model.parameters())
    model = _attach_lora_model(
        model,
        model_name=args.model,
        LoraConfig=LoraConfig,
        TaskType=TaskType,
        get_peft_model=get_peft_model,
    )
    trainable_parameter_count = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    cache_config = _generation_cache_config(model.config)
    cache_config.use_cache = False
    _configure_greedy_generation(model.generation_config)
    if checkpoint_gradients:
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
    train_dataset = _tokenized_dataset(Dataset, train_rows, tokenizer)
    validation_dataset = _tokenized_dataset(Dataset, validation_rows, tokenizer)
    steps_per_epoch = math.ceil(
        len(train_rows) / (spec["batch_size"] * spec["gradient_accumulation"])
    )
    eval_steps = max(1, round(steps_per_epoch * EVAL_EVERY_EPOCHS))
    short_run = args.smoke_test

    keep_checkpoints = args.save_model and not short_run
    effective_max_steps = _effective_max_steps(
        smoke_test=args.smoke_test,
        requested_steps=args.max_steps,
        train_records=len(train_rows),
        batch_size=spec["batch_size"],
        gradient_accumulation=spec["gradient_accumulation"],
    )
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        max_steps=effective_max_steps,
        per_device_train_batch_size=spec["batch_size"],
        per_device_eval_batch_size=spec.get("eval_batch_size", 1),
        gradient_accumulation_steps=spec["gradient_accumulation"],
        learning_rate=args.learning_rate,
        **_optimization_arguments(precision),
        gradient_checkpointing=checkpoint_gradients,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        eval_strategy="no" if short_run else "steps",
        eval_steps=eval_steps,
        save_strategy="steps" if keep_checkpoints else "no",
        save_steps=eval_steps,
        save_total_limit=1 if keep_checkpoints else None,
        save_only_model=True,
        load_best_model_at_end=keep_checkpoints,
        # Chọn checkpoint theo mất mát trên tập held-out. Sinh chữ được đánh giá
        # sau huấn luyện để tránh giải mã tuần tự ở mỗi mốc đánh giá.
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_strategy="steps",
        logging_steps=1 if args.smoke_test else 50,
        disable_tqdm=True,
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        predict_with_generate=False,
        # Đi cùng ``predict_with_generate=False`` để Trainer không giữ logits
        # của toàn bộ tập validation cho ``compute_metrics``.
        prediction_loss_only=True,
        generation_max_length=MAX_TARGET_LENGTH,
        generation_num_beams=1,
        torch_compile=args.compile,
        # CUDA graphs yêu cầu bộ đệm gradient có địa chỉ cố định qua các
        # micro-batch; chế độ ``-no-cudagraphs`` tránh ràng buộc này.
        torch_compile_mode=COMPILE_MODE if args.compile else None,
    )
    source_pad, target_pad = _fixed_pad_lengths(train_dataset, validation_dataset)

    class _FixedShapeCollator(DataCollatorForSeq2Seq):
        """Đệm mọi lô về cùng một hình dạng, nguồn và đích đệm riêng.

        Bộ gom lô sẵn có đệm theo câu dài nhất trong lô, nên mỗi lô một hình
        dạng. Lớp này đệm nhãn tới ``target_pad`` trước rồi để lớp cha đệm nguồn
        tới ``source_pad``; hai độ dài được giữ riêng để tránh đệm nguồn theo
        độ dài đích.
        """

        def __call__(self, features, return_tensors=None):
            for feature in features:
                labels = list(feature["labels"])
                feature["labels"] = labels + [self.label_pad_token_id] * (
                    target_pad - len(labels)
                )
            return super().__call__(features, return_tensors)

    collator = _FixedShapeCollator(
        tokenizer,
        model=model,
        padding="max_length",
        max_length=source_pad,
        pad_to_multiple_of=None,
        label_pad_token_id=-100,
    )
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=collator,
        processing_class=tokenizer,
        callbacks=(
            [EarlyStoppingCallback(early_stopping_patience=3)]
            if keep_checkpoints
            else None
        ),
    )
    if args.compile:
        trainer.add_callback(_stable_gradient_buffers(TrainerCallback, torch))

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    try:
        train_result = trainer.train()
    except (torch.OutOfMemoryError, RuntimeError) as exc:
        # Chuyển lỗi hết bộ nhớ thành hướng dẫn về các tham số giảm bộ nhớ.
        if "out of memory" not in str(exc).casefold():
            raise
        raise RuntimeError(
            "CUDA hết bộ nhớ khi huấn luyện "
            f"({args.model}, lô {spec['batch_size']}, "
            f"checkpointing {checkpoint_gradients}, "
            f"lô đánh giá {spec.get('eval_batch_size')}).\n"
            "Thử theo thứ tự:\n"
            "  --gradient-checkpointing on   (đổi ~1/4 tốc độ lấy bộ nhớ, "
            "KHÔNG đổi kết quả)\n"
            "  --batch-size 4                (lô hiệu dụng vẫn giữ 8 nhờ "
            "tích luỹ gradient)"
        ) from None
    inference_model = trainer.model
    adapter_source = trainer.state.best_model_checkpoint
    if adapter_source:
        # Rebuild the adapter on a clean pretrained base before merging it.
        trainer.model = None
        trainer.model_wrapped = None
        del inference_model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        inference_base = AutoModelForSeq2SeqLM.from_pretrained(
            snapshot,
            local_files_only=True,
            attn_implementation=spec["attention"],
            dtype=model_dtype,
            trust_remote_code=True,
        )
        inference_model = PeftModel.from_pretrained(
            inference_base,
            adapter_source,
            is_trainable=False,
        ).to(training_args.device)
    inference_model = inference_model.merge_and_unload()
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
        "dataset_records": dataset_report["dataset"]["records"],
        "dataset_manifest_sha256": sha256_file(args.dataset_dir / "manifest.json"),
        "batch_size": spec["batch_size"],
        "gradient_accumulation": spec["gradient_accumulation"],
        "source_pad_length": source_pad,
        "target_pad_length": target_pad,
        "dtype": precision["dtype"],
        "bf16": precision["bf16"],
        "fp16": precision["fp16"],
        "tf32": precision["tf32"],
        "torch_compile": bool(training_args.torch_compile),
        "torch_compile_mode": training_args.torch_compile_mode,
        "checkpoint_selection_metric": training_args.metric_for_best_model,
        "eval_generates_text": bool(training_args.predict_with_generate),
        "eval_batch_size": spec.get("eval_batch_size", 1),
        "gradient_checkpointing_spec": spec.get("gradient_checkpointing", False),
        "gradient_checkpointing": checkpoint_gradients,
        "generation_do_sample": False,
        "dropout_policy": "checkpoint_default",
        "fine_tuning_method": "peft_lora",
        "lora_rank": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "lora_dropout": LORA_DROPOUT,
        "lora_target_modules": len(
            _lora_target_modules(inference_model, args.model)
        ),
        "trainable_parameters": trainable_parameter_count,
        "base_parameters": base_parameter_count,
        "merged_artifact": True,
        # Đọc trực tiếp cấu hình đã truyền cho Trainer để metrics khớp cấu hình.
        **{
            key: value
            for key, value in _optimization_arguments(precision).items()
            if key in ("optim", "lr_scheduler_type", "warmup_steps", "weight_decay")
        },
        "learning_rate": args.learning_rate,
        "evaluation_every_epochs": EVAL_EVERY_EPOCHS,
        "early_stopping_patience": 3 if keep_checkpoints else None,
        "train_runtime_seconds": round(train_result.metrics.get("train_runtime", 0.0), 3),
        "train_loss": round(train_result.metrics.get("train_loss", 0.0), 6),
        "peak_vram_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "smoke_test": args.smoke_test,
        "unrepresentable_targets": len(lossy),
        "distinct_targets": len(targets),
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


#: Bội số để làm tròn độ dài đệm cố định.
#:
#: Hình dạng cố định giúp ``torch.compile`` tái sử dụng bản biên dịch thay vì
#: biên dịch lại cho mỗi lô có độ dài khác nhau.
PAD_MULTIPLE = 64


def _fixed_pad_lengths(*datasets) -> tuple[int, int]:
    """Độ dài đệm cố định, đo từ dữ liệu.

    Làm tròn độ dài lớn nhất lên bội số 64 để giữ hình dạng cố định mà không
    đệm mọi lô tới trần cắt.

    Đo từ dữ liệu để đích không bị cắt khi dữ liệu có câu dài hơn.
    """

    longest_source = 0
    longest_target = 0
    for dataset in datasets:
        for row in dataset:
            longest_source = max(longest_source, len(row["input_ids"]))
            longest_target = max(longest_target, len(row["labels"]))
    return (
        min(MAX_SOURCE_LENGTH, math.ceil(longest_source / PAD_MULTIPLE) * PAD_MULTIPLE),
        min(MAX_TARGET_LENGTH, math.ceil(longest_target / PAD_MULTIPLE) * PAD_MULTIPLE),
    )


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


def _generation_cache_config(config):
    """Return the config object that owns ``use_cache``.

    Conventional seq2seq models expose it on the top-level config, whereas
    T5Gemma2 keeps it on its decoder config.
    """

    if hasattr(config, "use_cache"):
        return config
    decoder = getattr(config, "decoder", None)
    if decoder is None or not hasattr(decoder, "use_cache"):
        raise AttributeError("seq2seq model config does not expose use_cache")
    return decoder


def _generate_rows(model, tokenizer, rows, torch, *, batch_size: int) -> list[str]:
    """Generate from a normally reloaded checkpoint, independent of Trainer state."""

    model.eval()
    cache_config = _generation_cache_config(model.config)
    use_cache = cache_config.use_cache
    cache_config.use_cache = True
    predictions = []
    try:
        # ``no_grad`` chứ không phải ``inference_mode``: tensor của chế độ suy
        # luận không mang bộ đếm phiên bản, thứ mà model đã gộp LoRA cần khi sinh.
        with torch.no_grad():
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
        cache_config.use_cache = use_cache
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


def _effective_max_steps(
    *,
    smoke_test: bool,
    requested_steps: int,
    train_records: int,
    batch_size: int,
    gradient_accumulation: int,
) -> int:
    if not smoke_test:
        return requested_steps
    return math.ceil(train_records / (batch_size * gradient_accumulation))


def _require_training_ready(
    readiness: dict,
    *,
    smoke_test: bool,
) -> None:
    if readiness.get("ready") or smoke_test:
        return
    codes = [gap.get("code", "unknown") for gap in readiness.get("gaps", [])]
    raise RuntimeError(
        "dataset is not ready for full training: " + ", ".join(codes)
    )


def _should_checkpoint_gradients(spec_default: bool) -> bool:
    """Chọn checkpointing gradient theo VRAM của máy đang chạy.

    Checkpointing tính lại activation để giảm bộ nhớ mà không thay đổi phép tính.
    """

    try:
        import torch
    except ImportError:
        return spec_default
    if not torch.cuda.is_available():
        return spec_default
    return torch.cuda.get_device_properties(0).total_memory < 16 * 1024**3


def _precision_policy(
    *,
    cuda_available: bool,
    bf16_supported: bool,
    compute_capability: tuple[int, int] | None,
) -> dict[str, str | bool]:
    bf16 = cuda_available and bf16_supported
    return {
        "dtype": "bfloat16" if bf16 else "float16" if cuda_available else "float32",
        "bf16": bf16,
        "fp16": cuda_available and not bf16,
        "tf32": cuda_available
        and compute_capability is not None
        and compute_capability[0] >= 8,
    }


def _optimization_arguments(
    precision: dict[str, str | bool],
) -> dict[str, object]:
    return {
        "lr_scheduler_type": "cosine",
        "warmup_steps": 0.1,
        "weight_decay": 0.005,
        # LoRA chỉ tối ưu một phần nhỏ tham số, nên dùng optimizer fused không
        # cần trạng thái optimizer nén.
        "optim": "adamw_torch_fused",
        "bf16": precision["bf16"],
        "fp16": precision["fp16"],
        "tf32": precision["tf32"],
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR / "models")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="ép lô vật lý; bỏ trống thì lấy theo model, tích luỹ gradient bù lại để lô hiệu dụng không đổi",
    )
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="tắt torch.compile; lối lui khi một model không biên dịch được",
    )
    parser.add_argument("--save-model", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    # Hai cờ chỉ dùng để thử máy: chạy vài bước trên vài dòng dữ liệu để biết
    # môi trường dựng được model hay không, trước khi tiêu một lượt máy thuê.
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--max-steps", type=int, default=-1)
    args = parser.parse_args(argv)
    args.compile = not args.no_compile
    return args


def main() -> None:
    train(_parse_args())


if __name__ == "__main__":
    main()
