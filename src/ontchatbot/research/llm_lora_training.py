"""QLoRA fine-tuning for a causal LLM that emits canonical SPARQL.

This path is intentionally independent from :mod:`ontchatbot.research.training`,
which trains encoder-decoder models.  Sharing the dataset and final evaluator is
useful; sharing tokenization, collators, or Trainer configuration would make the
causal-LM/seq2seq comparison ambiguous.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

# This must be set before anything imports torch and initializes CUDA.  Respect
# an explicit operator override while making the allocator mode safe by default
# for the small, fragmentation-sensitive GPUs targeted by this training path.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError

from ..runtime.text import normalize_model_input
from ..settings import ARTIFACTS_DIR, DATASET_DIR
from .dataset import load_release
from .reporting import build_dataset_report, sha256_file
from .training import _require_training_ready
from ..runtime.sparql import load_ontology

MODEL_ID = "Qwen/Qwen3.5-2B"
MODEL_REVISION = "15852e8c16360a2fea060d615a32b45270f8a8fc"
# Sum of the files in the pinned Hub snapshot.  This lets the offline guard tell
# the operator what approval would be needed without contacting the Hub.
EXPECTED_DOWNLOAD_BYTES = 4_571_274_023

MAX_SEQUENCE_LENGTH = 320
EFFECTIVE_BATCH_SIZE = 8
SMOKE_STEPS = 1
DEFAULT_EPOCHS = 3.0
LORA_DROPOUT = 0.05
ATTENTION_LORA_TARGET_MODULES = (
    # Qwen3.5 linear-attention blocks.
    "in_proj_qkv",
    "in_proj_z",
    "in_proj_b",
    "in_proj_a",
    "out_proj",
    # Qwen3.5 full-attention blocks.
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
)
FULL_LORA_TARGET_MODULES = (
    *ATTENTION_LORA_TARGET_MODULES,
    # MLP blocks in both layer types.
    "gate_proj",
    "up_proj",
    "down_proj",
)

SYSTEM_PROMPT = (
    "Chuyển câu hỏi học vụ thành đúng một truy vấn SPARQL thuộc danh mục. "
    "Chỉ trả về truy vấn SPARQL, không giải thích."
)


@dataclass(frozen=True)
class BatchPlan:
    per_device_batch_size: int
    gradient_accumulation_steps: int


@dataclass(frozen=True)
class LoraSpec:
    rank: int
    alpha: int
    target_modules: tuple[str, ...]


class CudaAttemptOOM(RuntimeError):
    """OOM stripped of the failed model traceback so the next attempt can free it."""

    def __init__(self, *, stage: str, detail: str) -> None:
        super().__init__(f"CUDA OOM during {stage}: {detail}")
        self.stage = stage


class TargetOnlyDataCollator:
    """Right-pad a causal-LM batch while keeping every pad label at ``-100``."""

    def __init__(self, *, pad_token_id: int, pad_to_multiple_of: int = 8) -> None:
        if pad_token_id is None:
            raise ValueError("the tokenizer must define pad_token_id")
        self.pad_token_id = pad_token_id
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, features: Sequence[dict[str, list[int]]]):
        import torch

        if not features:
            raise ValueError("cannot collate an empty batch")
        longest = max(len(feature["input_ids"]) for feature in features)
        padded_length = (
            math.ceil(longest / self.pad_to_multiple_of) * self.pad_to_multiple_of
        )
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for feature in features:
            length = len(feature["input_ids"])
            if not (length == len(feature["attention_mask"]) == len(feature["labels"])):
                raise ValueError("input_ids, attention_mask, and labels must align")
            padding = padded_length - length
            batch["input_ids"].append(
                feature["input_ids"] + [self.pad_token_id] * padding
            )
            batch["attention_mask"].append(feature["attention_mask"] + [0] * padding)
            batch["labels"].append(feature["labels"] + [-100] * padding)
        return {
            name: torch.tensor(values, dtype=torch.long)
            for name, values in batch.items()
        }


def _flash_attention_available() -> bool:
    """Report whether the optional flash-attn wheel is importable."""

    from importlib.util import find_spec

    return find_spec("flash_attn") is not None


def _cached_snapshot(*, allow_download: bool = False) -> Path:
    """Tìm model đã ghim. KHÔNG tự tải trừ khi người chạy nói rõ là được.

    Mặc định là chặn, và chặn có lý do: 4,57 GB trên một máy thuê tính tiền theo
    giờ, tải âm thầm giữa lượt huấn luyện thì vừa tốn vừa khó truy. Nhưng máy vừa
    clone về thì chưa có gì trong cache, nên phải có đường mở CÓ CHỦ Ý -
    ``benchmark_llm`` vốn đã có ``--allow-download``, bên này thiếu nên người chạy
    kẹt cứng không có lối nào ngoài việc tự đoán lệnh tải.
    """

    try:
        return Path(
            snapshot_download(
                MODEL_ID,
                revision=MODEL_REVISION,
                local_files_only=not allow_download,
            )
        )
    except LocalEntryNotFoundError as exc:
        gb = EXPECTED_DOWNLOAD_BYTES / 1_000_000_000
        gib = EXPECTED_DOWNLOAD_BYTES / (1024**3)
        raise RuntimeError(
            f"{MODEL_ID}@{MODEL_REVISION} is not complete in the local cache; "
            f"stopped without downloading. Approval would be required for about "
            f"{gb:.2f} GB ({gib:.2f} GiB). Chạy lại với --allow-download nếu "
            f"muốn cho phép tải."
        ) from exc


def _prompt_ids(tokenizer, question: str) -> list[int]:
    encoded = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": normalize_model_input(question)},
        ],
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if isinstance(encoded, Mapping):
        encoded = encoded["input_ids"]
    return list(encoded)


def encode_training_example(
    tokenizer,
    row: dict[str, str],
    *,
    max_length: int = MAX_SEQUENCE_LENGTH,
) -> dict[str, list[int]]:
    """Encode one row and supervise only target tokens plus their final EOS."""

    prompt = _prompt_ids(tokenizer, row["input"])
    target = list(
        tokenizer(row["target"], add_special_tokens=False)["input_ids"]
    )
    if tokenizer.eos_token_id is None:
        raise ValueError("the tokenizer must define eos_token_id")
    if not target or target[-1] != tokenizer.eos_token_id:
        target.append(tokenizer.eos_token_id)
    input_ids = prompt + target
    if len(input_ids) > max_length:
        raise ValueError(
            f"{row.get('id', '<unknown>')}: {len(input_ids)} tokens exceed "
            f"MAX_SEQUENCE_LENGTH={max_length}; refusing to truncate the target"
        )
    labels = [-100] * len(prompt) + target
    if any(label != -100 for label in labels[: len(prompt)]):  # defensive invariant
        raise AssertionError("prompt tokens must be excluded from the loss")
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
    }


def _batch_plans(
    requested: int | None, *, checkpointing: bool = True
) -> tuple[BatchPlan, ...]:
    """Thang lô để thử, từ lớn xuống nhỏ.

    Bỏ activation đi (checkpointing) thì lô 8 vừa; giữ activation lại thì không.
    Đo trên L4 24 GB ngày 15/8/2026, chuỗi dài nhất 266 token: tắt checkpointing
    rồi thử lô 8 thì đỉnh **20,30 / 22,0 GiB rồi tràn**, lùi về lô 4 chỉ còn
    13,44 GiB. Bắt đầu từ 8 trong trường hợp đó là chắc chắn tràn, và mỗi lần
    tràn phải nạp lại model từ đầu.

    Lô hiệu dụng không đổi dù bắt đầu ở đâu - phần chênh được bù bằng tích luỹ
    gradient - nên bỏ nấc 8 không làm đổi kết quả huấn luyện, chỉ bớt một lượt
    nạp model vô ích.
    """

    if requested is not None:
        sizes: tuple[int, ...] = (requested,)
    elif checkpointing:
        sizes = (EFFECTIVE_BATCH_SIZE, 4, 2, 1)
    else:
        sizes = (4, 2, 1)
    return tuple(
        BatchPlan(
            per_device_batch_size=size,
            gradient_accumulation_steps=EFFECTIVE_BATCH_SIZE // size,
        )
        for size in sizes
    )


def _lora_spec(profile: str) -> LoraSpec:
    if profile == "attention-r8":
        return LoraSpec(
            rank=8,
            alpha=16,
            target_modules=ATTENTION_LORA_TARGET_MODULES,
        )
    if profile == "full-r16":
        return LoraSpec(
            rank=16,
            alpha=32,
            target_modules=FULL_LORA_TARGET_MODULES,
        )
    raise ValueError(f"unknown LoRA profile: {profile}")


def _is_cuda_oom(exc: BaseException) -> bool:
    return "out of memory" in str(exc).casefold()


def _cuda_memory_record(torch, stage: str) -> dict[str, int | str]:
    free_bytes, total_bytes = torch.cuda.mem_get_info()
    stats = torch.cuda.memory_stats()
    allocated = torch.cuda.memory_allocated()
    reserved = torch.cuda.memory_reserved()
    return {
        "stage": stage,
        "allocated_bytes": allocated,
        "reserved_bytes": reserved,
        "reserved_unallocated_bytes": max(0, reserved - allocated),
        "physical_free_bytes": free_bytes,
        "physical_total_bytes": total_bytes,
        "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
        "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
        "inactive_split_bytes": stats.get(
            "inactive_split_bytes.all.current", 0
        ),
        "peak_inactive_split_bytes": stats.get(
            "inactive_split_bytes.all.peak", 0
        ),
    }


def _record_cuda_memory(torch, records: list[dict], stage: str) -> dict:
    torch.cuda.synchronize()
    record = _cuda_memory_record(torch, stage)
    records.append(record)
    print(f"CUDA_MEMORY {json.dumps(record, sort_keys=True)}", flush=True)
    return record


def _tied_weight_status(model) -> dict[str, Any]:
    input_embeddings = model.get_input_embeddings()
    output_embeddings = model.get_output_embeddings()
    if input_embeddings is None or output_embeddings is None:
        raise RuntimeError("model must expose input embeddings and an lm_head")
    input_weight = input_embeddings.weight
    output_weight = output_embeddings.weight
    return {
        "tied": input_weight is output_weight,
        "dtype": str(input_weight.dtype).removeprefix("torch."),
        "parameter_class": type(input_weight).__name__,
        "logical_parameters": input_weight.numel(),
        "storage_bytes": input_weight.numel() * input_weight.element_size(),
        "requires_grad": input_weight.requires_grad,
    }


def _cast_tied_weight_to_dtype(model, dtype) -> dict[str, Any]:
    status = _tied_weight_status(model)
    if not status["tied"]:
        raise RuntimeError(
            "input embedding and lm_head are not tied; refusing a partial dtype cast"
        )
    if status["parameter_class"] == "Params4bit":
        raise RuntimeError("tied embedding/lm_head is already a packed 4-bit parameter")
    if status["requires_grad"]:
        raise RuntimeError("tied embedding/lm_head must be frozen before dtype cast")

    weight = model.get_input_embeddings().weight
    before_bytes = status["storage_bytes"]
    weight.data = weight.data.to(dtype=dtype)
    after = _tied_weight_status(model)
    if not after["tied"]:
        raise RuntimeError("tied embedding/lm_head identity changed during dtype cast")
    return {
        **after,
        "before_bytes": before_bytes,
        "after_bytes": after["storage_bytes"],
        "saved_bytes": before_bytes - after["storage_bytes"],
    }



#: Ngưỡng VRAM để tự tắt gradient checkpointing.
#:
#: Checkpointing đánh đổi TỐC ĐỘ lấy BỘ NHỚ: nó bỏ activation rồi tính lại ở lượt
#: truyền ngược, thường mất 30-40% tốc độ. Trên card 6 GB đó là đánh đổi bắt buộc
#: - không bật thì batch 2 cũng tràn. Trên L4 24 GB thì đó là trả giá mà không
#: mua gì: batch 8 nằm gọn trong bộ nhớ.
#:
#: Kết quả huấn luyện KHÔNG đổi. Đây là phép đánh đổi thuần tuý bộ nhớ - phép tính
#: giống hệt, gradient giống hệt.
#:
#: 16 GiB là ngưỡng chia hai loại máy dự án thực sự dùng: 6 GB ở local, 24 GB trên
#: server thuê. Không có máy nào nằm giữa để phải cân nhắc.
GRADIENT_CHECKPOINT_VRAM_THRESHOLD = 16 * 1024**3


def _should_checkpoint_gradients(torch, choice: str) -> bool:
    """Có nên bỏ activation để tính lại không - hỏi theo VRAM của máy đang chạy."""

    if choice == "on":
        return True
    if choice == "off":
        return False
    if not torch.cuda.is_available():
        return True
    total = torch.cuda.get_device_properties(0).total_memory
    return total < GRADIENT_CHECKPOINT_VRAM_THRESHOLD



def _resolve_base_precision(choice: str) -> str:
    """Nén 4-bit trọng số gốc hay giữ bf16 - hỏi theo VRAM của máy đang chạy.

    Cùng cách chọn với gradient checkpointing, và cùng lý do: một cờ sinh ra cho
    card 6 GB không nên đi theo dự án lên card 24 GB. Nén 4-bit bắt bitsandbytes
    giải nén trọng số ở MỖI lượt truyền, mà lô nhỏ với chuỗi ngắn thì không có
    đủ phép tính để chia đều chi phí đó - huấn luyện trả giá cả xuôi lẫn ngược.

    Ngưỡng dùng chung với checkpointing: model 1,2 tỉ tham số ở bf16 tốn khoảng
    2,4 GB, nên 16 GiB là dư dả, còn 6 GB thì 4-bit là cách DUY NHẤT vừa.
    """

    if choice != "auto":
        return choice
    total = _gpu_total_bytes()
    if total is None:
        return "4bit"
    return "bf16" if total >= GRADIENT_CHECKPOINT_VRAM_THRESHOLD else "4bit"


def _gpu_total_bytes() -> int | None:
    """VRAM của máy đang chạy, hoặc None nếu không có GPU."""

    try:
        import torch
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None
    return int(torch.cuda.get_device_properties(0).total_memory)



def _checkpointing_for_log(args) -> bool | None:
    """Quyết định checkpointing, tính riêng để ghi log trước khi vào vòng thử lô."""

    try:
        import torch
    except ImportError:
        return None
    return _should_checkpoint_gradients(torch, args.gradient_checkpointing)


def _compute_dtype(torch):
    # Turing reports software bf16 support in some stacks.  Native bf16 starts
    # at compute capability 8, so a 6 GB pre-Ampere card must use fp16.
    if torch.cuda.get_device_capability()[0] >= 8:
        return torch.bfloat16
    return torch.float16


def _load_rows(
    *, smoke_test: bool, dataset_dir: Path, allow_incomplete: bool = False
) -> list[dict]:
    release = load_release(dataset_dir)
    if not smoke_test:
        report = build_dataset_report(
            release,
            load_ontology(),
            dataset_dir=dataset_dir,
        )
        readiness = report["training_readiness"]
        if allow_incomplete and not readiness.get("ready"):
            # Announce the gaps rather than swallowing them: an adapter trained
            # through this branch is exploratory, not a release candidate.
            gaps = [gap.get("code", "unknown") for gap in readiness.get("gaps", [])]
            print(f"WARNING: training with readiness gaps: {', '.join(gaps)}")
            print(json.dumps(readiness.get("gaps", []), ensure_ascii=False))
        else:
            _require_training_ready(readiness, smoke_test=False)
    return release["train"]


def _run_attempt(
    *,
    args: argparse.Namespace,
    snapshot: Path,
    tokenizer,
    encoded_rows: list[dict[str, list[int]]],
    train_record_count: int,
    plan: BatchPlan,
) -> tuple[dict[str, Any], Any]:
    import torch
    from peft import (
        LoraConfig,
        TaskType,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
    from transformers import (
        AutoConfig,
        AutoModelForCausalLM,
        BitsAndBytesConfig,
        Qwen3_5ForCausalLM,
        Trainer,
        TrainingArguments,
    )

    compute_dtype = _compute_dtype(torch)
    checkpoint_gradients = _should_checkpoint_gradients(
        torch, args.gradient_checkpointing
    )
    lora = _lora_spec(args.lora_profile)
    # NÉN 4-BIT LÀ TUỲ CHỌN, VÀ KHÔNG CÒN LÀ MẶC ĐỊNH.
    #
    # Nó sinh ra cho card 6 GB. Trên card lớn nó chỉ lấy đi tốc độ:
    # bitsandbytes giải nén trọng số ở MỖI lượt truyền, mà lô nhỏ với chuỗi
    # ngắn thì gần như không có phép tính nào để chia đều chi phí đó - huấn
    # luyện trả giá hai lần, xuôi và ngược. Model 1,2 tỉ tham số ở bf16 chỉ tốn
    # khoảng 2,4 GB nên L4 24 GB thừa sức giữ nguyên.
    #
    # Vẫn giữ đường 4-bit vì card 6 GB không nạp nổi bf16.
    quantize = args.base_precision == "4bit"
    quantization = (
        BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
            # Lớp lm_head phải ở dạng đầy đủ: bitsandbytes đòi trọng số 4-bit đã
            # đóng gói, còn lm_head buộc nhau trọng số với lớp nhúng nên không đóng
            # gói. Lượng tử hoá nó thì vấp assert ngay lượt truyền xuôi đầu tiên.
            llm_int8_skip_modules=["lm_head"],
        )
        if quantize
        else None
    )
    memory_records: list[dict] = []
    model = None
    trainer = None
    stage = "before_model_load"
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    _record_cuda_memory(torch, memory_records, stage)

    try:
        stage = "model_load"
        load_kwargs = {
            "local_files_only": True,
            "dtype": compute_dtype,
            "device_map": {"": torch.cuda.current_device()},
            "low_cpu_mem_usage": True,
        }
        if quantization is not None:
            load_kwargs["quantization_config"] = quantization
        # FlashAttention-2 is optional: the wheel is pinned to one CUDA/torch/
        # Python combination, so a checkout on another machine will not have it.
        # It buys headroom during training, not during adapter construction,
        # which is where this path peaks - so its absence is not fatal.
        if _flash_attention_available():
            load_kwargs["attn_implementation"] = "flash_attention_2"
        if args.model_profile == "text-only":
            full_config = AutoConfig.from_pretrained(snapshot, local_files_only=True)
            model = Qwen3_5ForCausalLM.from_pretrained(
                snapshot,
                config=full_config.text_config,
                **load_kwargs,
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(snapshot, **load_kwargs)
        _record_cuda_memory(torch, memory_records, "after_model_load")

        model.config.use_cache = False
        stage = "kbit_prepare"
        if quantize:
            model = prepare_model_for_kbit_training(
                model,
                use_gradient_checkpointing=checkpoint_gradients,
                gradient_checkpointing_kwargs={"use_reentrant": False},
            )
        else:
            # ``prepare_model_for_kbit_training`` chỉ có nghĩa với trọng số đã
            # nén: nó gỡ lớp nén ra khỏi đồ thị gradient rồi ép vài lớp lên
            # fp32. Không nén thì nó thừa, nhưng hai việc nó làm thêm thì vẫn
            # cần - đóng băng trọng số gốc và bật checkpointing.
            for parameter in model.parameters():
                parameter.requires_grad = False
            if checkpoint_gradients:
                model.gradient_checkpointing_enable(
                    gradient_checkpointing_kwargs={"use_reentrant": False}
                )
                model.enable_input_require_grads()
        _record_cuda_memory(torch, memory_records, "after_kbit_prepare")

        stage = "tied_weight_cast"
        tied_weight = _tied_weight_status(model)
        if args.keep_tied_weight_fp32 or not quantize:
            tied_weight = {
                **tied_weight,
                "before_bytes": tied_weight["storage_bytes"],
                "after_bytes": tied_weight["storage_bytes"],
                "saved_bytes": 0,
            }
        else:
            tied_weight = _cast_tied_weight_to_dtype(model, compute_dtype)
        print(f"TIED_WEIGHT {json.dumps(tied_weight, sort_keys=True)}", flush=True)
        gc.collect()
        torch.cuda.empty_cache()
        _record_cuda_memory(torch, memory_records, "after_tied_weight_cast")

        lora_projection_layers = sum(
            1
            for name, module in model.named_modules()
            if name.rsplit(".", 1)[-1] in lora.target_modules
            and hasattr(module, "in_features")
            and hasattr(module, "out_features")
        )
        stage = "adapter"
        model = get_peft_model(
            model,
            LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=lora.rank,
                lora_alpha=lora.alpha,
                lora_dropout=LORA_DROPOUT,
                bias="none",
                target_modules=list(lora.target_modules),
            ),
        )
        _record_cuda_memory(torch, memory_records, "after_adapter")
        trainable_parameters = sum(
            parameter.numel()
            for parameter in model.parameters()
            if parameter.requires_grad
        )
        total_parameters = sum(parameter.numel() for parameter in model.parameters())

        with tempfile.TemporaryDirectory(
            prefix="ontchatbot-qwen-lora-"
        ) as trainer_dir:
            training_args = TrainingArguments(
                output_dir=trainer_dir,
                num_train_epochs=args.epochs,
                max_steps=SMOKE_STEPS if args.smoke_test else -1,
                per_device_train_batch_size=plan.per_device_batch_size,
                gradient_accumulation_steps=plan.gradient_accumulation_steps,
                learning_rate=args.learning_rate,
                lr_scheduler_type="cosine",
                # transformers 5.x accepts fractional warmup through this field.
                warmup_steps=0.03,
                weight_decay=0.0,
                # Đo trên 60 bước, card 6 GB, bf16: adamw_torch 4,902 · fused
                # 4,914 · paged_adamw_8bit 4,940 giây/bước. Chênh 0,8%, tức
                # nhiễu. LoRA học 3,69 triệu tham số còn mỗi bước phải đẩy qua
                # 1,2 tỉ trọng số đóng băng, nên bước optimizer không phải chỗ
                # tốn thời gian. Chốt bản fused, đừng đo lại.
                optim="adamw_torch_fused",
                max_grad_norm=0.3,
                gradient_checkpointing=checkpoint_gradients,
                gradient_checkpointing_kwargs={"use_reentrant": False},
                bf16=compute_dtype is torch.bfloat16,
                fp16=compute_dtype is torch.float16,
                tf32=torch.cuda.get_device_capability()[0] >= 8,
                torch_compile=args.torch_compile,
                eval_strategy="no",
                save_strategy="no",
                logging_strategy="steps",
                logging_steps=1 if args.smoke_test else 20,
                disable_tqdm=True,
                report_to="none",
                seed=args.seed,
                data_seed=args.seed,
                remove_unused_columns=False,
                dataloader_num_workers=0,
            )
            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=encoded_rows,
                data_collator=TargetOnlyDataCollator(
                    pad_token_id=tokenizer.pad_token_id,
                    pad_to_multiple_of=8,
                ),
            )
            initialization = _record_cuda_memory(
                torch, memory_records, "after_trainer_init"
            )
            initialization_peak_allocated = initialization["peak_allocated_bytes"]
            initialization_peak_reserved = initialization["peak_reserved_bytes"]
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()
            stage = "training"
            started = time.monotonic()
            result = trainer.train()
            torch.cuda.synchronize()
            elapsed = time.monotonic() - started
            _record_cuda_memory(torch, memory_records, "after_train")

            steps = trainer.state.global_step
            if steps < 1:
                raise RuntimeError("Trainer completed without an optimizer step")
            seconds_per_step = elapsed / steps
            steps_per_epoch = math.ceil(train_record_count / EFFECTIVE_BATCH_SIZE)
            metrics = {
                "model_id": MODEL_ID,
                "revision": MODEL_REVISION,
                "model_profile": args.model_profile,
                "model_cached": True,
                "cache_bytes": EXPECTED_DOWNLOAD_BYTES,
                "dataset_train_records": train_record_count,
                "dataset_manifest_sha256": sha256_file(
                    args.dataset_dir / "manifest.json"
                ),
                "smoke_test": args.smoke_test,
                "smoke_steps": SMOKE_STEPS if args.smoke_test else None,
                "evaluation": False,
                "model_saved": False,
                "optimizer_steps": steps,
                "epochs": args.epochs,
                "per_device_batch_size": plan.per_device_batch_size,
                "gradient_accumulation_steps": plan.gradient_accumulation_steps,
                "effective_batch_size": EFFECTIVE_BATCH_SIZE,
                "max_sequence_length": MAX_SEQUENCE_LENGTH,
                "dynamic_padding_multiple": 8,
                "gradient_checkpointing": checkpoint_gradients,
                "group_by_length": False,
                # Bộ chấm ĐỌC ô này để chọn nền trọng số, nên nó phải nói đúng
                # sự thật: adapter học bù cho một nền cụ thể, chấm trên nền khác
                # là chấm một model khác mà không có triệu chứng gì.
                "quantization": (
                    "4-bit NF4 double-quant; tied lm_head skipped"
                    if quantize
                    else None
                ),
                "base_precision": args.base_precision,
                "allocator_conf": os.environ.get("PYTORCH_CUDA_ALLOC_CONF"),
                "compute_dtype": str(compute_dtype).removeprefix("torch."),
                "lora_profile": args.lora_profile,
                "lora_rank": lora.rank,
                "lora_alpha": lora.alpha,
                "lora_dropout": LORA_DROPOUT,
                "lora_target_modules": list(lora.target_modules),
                "lora_projection_layers": lora_projection_layers,
                "trainable_parameters": trainable_parameters,
                "total_parameters": total_parameters,
                "tied_weight": tied_weight,
                "train_loss": result.metrics.get("train_loss"),
                "elapsed_seconds": round(elapsed, 3),
                "seconds_per_optimizer_step": round(seconds_per_step, 3),
                "steps_per_epoch": steps_per_epoch,
                "estimated_seconds_per_epoch": round(
                    seconds_per_step * steps_per_epoch, 1
                ),
                "estimated_full_run_seconds": round(
                    seconds_per_step * steps_per_epoch * args.epochs, 1
                ),
                "initialization_peak_allocated_bytes": initialization_peak_allocated,
                "initialization_peak_reserved_bytes": initialization_peak_reserved,
                "training_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "training_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "cuda_memory_records": memory_records,
                "gpu": torch.cuda.get_device_name(),
                "torch_version": torch.__version__,
            }
        return metrics, model
    except (torch.cuda.OutOfMemoryError, RuntimeError) as exc:
        if not _is_cuda_oom(exc):
            raise
        try:
            _record_cuda_memory(torch, memory_records, f"oom_{stage}")
        except Exception:
            pass
        detail = str(exc)
        trainer = None
        model = None
        gc.collect()
        torch.cuda.empty_cache()
        raise CudaAttemptOOM(stage=stage, detail=detail) from None


def train(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from transformers import AutoTokenizer

    snapshot = _cached_snapshot(allow_download=args.allow_download)
    if args.smoke_test and args.save_adapter:
        raise ValueError("smoke test never saves a model")
    if not torch.cuda.is_available():
        raise RuntimeError(
            f"{MODEL_ID} is present in the local cache at {snapshot}, but CUDA is "
            "not available; refusing to run a misleading CPU smoke test"
        )
    # Chốt "auto" thành giá trị thật NGAY ĐÂY, trước khi bất cứ ai đọc nó. Để
    # mỗi chỗ tự suy lại là mở đường cho hai chỗ suy ra hai kiểu.
    args.base_precision = _resolve_base_precision(args.base_precision)
    rows = _load_rows(
        smoke_test=args.smoke_test,
        dataset_dir=args.dataset_dir,
        allow_incomplete=args.allow_incomplete_coverage,
    )
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    tokenizer.padding_side = "right"
    encoded = [encode_training_example(tokenizer, row) for row in rows]
    longest_sequence = max(len(row["input_ids"]) for row in encoded)
    if args.smoke_test:
        # One optimizer step over the longest rows allocates model, adapter,
        # gradients, and optimizer state without turning a probe into training.
        keep = SMOKE_STEPS * EFFECTIVE_BATCH_SIZE
        encoded = sorted(
            encoded,
            key=lambda row: len(row["input_ids"]),
            reverse=True,
        )[:keep]

    print(
        "RUN_CONFIG "
        + json.dumps(
            {
                "allocator_conf": os.environ.get("PYTORCH_CUDA_ALLOC_CONF"),
                "lora_profile": args.lora_profile,
                "optim": "adamw_torch_fused",
                "torch_compile": args.torch_compile,
                "model_profile": args.model_profile,
                "keep_tied_weight_fp32": args.keep_tied_weight_fp32,
                # Ghi CẢ lựa chọn lẫn kết quả suy ra. Đọc log nguội mà chỉ thấy
                # "auto" thì không biết máy đó đã bật hay tắt, mà đó lại là thứ
                # giải thích phần lớn chênh lệch tốc độ giữa hai lượt chạy.
                "base_precision": args.base_precision,
                "gradient_checkpointing_choice": args.gradient_checkpointing,
                "gradient_checkpointing_effective": _checkpointing_for_log(args),
                "gpu_total_bytes": _gpu_total_bytes(),
                "smoke_test": args.smoke_test,
                "smoke_steps": SMOKE_STEPS if args.smoke_test else None,
            },
            sort_keys=True,
        ),
        flush=True,
    )

    last_oom_detail: str | None = None
    for plan in _batch_plans(
        args.batch_size, checkpointing=_checkpointing_for_log(args)
    ):
        model = None
        try:
            metrics, model = _run_attempt(
                args=args,
                snapshot=snapshot,
                tokenizer=tokenizer,
                encoded_rows=encoded,
                train_record_count=len(rows),
                plan=plan,
            )
            metrics["longest_training_sequence"] = longest_sequence
            if args.save_adapter:
                output_dir = Path(args.output_dir)
                if output_dir.exists() and (
                    not output_dir.is_dir() or any(output_dir.iterdir())
                ):
                    raise RuntimeError(
                        f"adapter output directory is not empty: {output_dir}"
                    )
                output_dir.mkdir(parents=True, exist_ok=True)
                model.save_pretrained(output_dir)
                tokenizer.save_pretrained(output_dir)
                metrics["model_saved"] = True
                (output_dir / "training_metrics.json").write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(json.dumps(metrics, ensure_ascii=False, indent=2), flush=True)
            return metrics
        except CudaAttemptOOM as exc:
            last_oom_detail = str(exc)
            if exc.stage != "training":
                print(
                    f"CUDA OOM during {exc.stage}; physical batch size cannot "
                    "change model/adapter initialization, so no batch retry.",
                    flush=True,
                )
                break
            if plan.per_device_batch_size == 1 or args.batch_size is not None:
                break
            print(
                f"CUDA OOM at batch {plan.per_device_batch_size}; retrying with a "
                "smaller physical batch while preserving effective batch 8.",
                flush=True,
            )
        finally:
            del model
            gc.collect()
            torch.cuda.empty_cache()
    raise RuntimeError(f"CUDA OOM: {last_oom_detail}") from None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "llm-lora" / "qwen3.5-2b",
    )
    parser.add_argument("--epochs", type=float, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--batch-size",
        type=int,
        choices=(1, 2, 4, 8),
        default=None,
        help="physical batch; omitted means try 8, 4, 2, 1 on CUDA OOM",
    )
    parser.add_argument(
        "--allow-incomplete-coverage",
        action="store_true",
        help=(
            "train despite readiness gaps. For exploratory runs only - the "
            "resulting adapter is not a release candidate, and the gaps are "
            "printed so the run cannot be mistaken for a clean one"
        ),
    )
    parser.add_argument(
        "--torch-compile",
        action="store_true",
        help="biên dịch đồ thị huấn luyện; ĐO trước khi tin, xem docs/TRAINING.md",
    )
    parser.add_argument(
        "--base-precision",
        choices=("auto", "bf16", "4bit"),
        default="auto",
        help=(
            "độ chính xác trọng số GỐC. Mặc định tự chọn: bf16 khi VRAM ≥ 16 GiB "
            "(LoRA thường, nhanh hơn), 4bit khi dưới (QLoRA, cách duy nhất vừa "
            "card 6 GB)."
        ),
    )
    parser.add_argument(
        "--lora-profile",
        choices=("attention-r8", "full-r16"),
        default="attention-r8",
        help="attention-r8 is the training default; full-r16 is only for A/B memory",
    )
    parser.add_argument(
        "--model-profile",
        choices=("text-only", "full"),
        default="text-only",
        help="load only Qwen's language model or the full unused multimodal tower",
    )
    parser.add_argument(
        "--keep-tied-weight-fp32",
        action="store_true",
        help="A/B probe only: do not return the frozen tied embedding/lm_head to compute dtype",
    )
    parser.add_argument(
        "--gradient-checkpointing",
        choices=("auto", "on", "off"),
        default="auto",
        help=(
            "auto: bật khi VRAM dưới 16 GiB, tắt khi trên. Tắt thì nhanh hơn "
            "30-40%% mà kết quả không đổi, nhưng tốn bộ nhớ hơn hẳn."
        ),
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help=(
            "cho phép tải model đã ghim từ Hugging Face nếu cache chưa có "
            "(khoảng 4,57 GB). Mặc định là KHÔNG tải."
        ),
    )
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--save-adapter", action="store_true")
    args = parser.parse_args(argv)
    if args.smoke_test and args.save_adapter:
        parser.error("smoke test never saves a model")
    if args.epochs <= 0:
        parser.error("--epochs must be positive")
    return args


def main() -> None:
    train(_parse_args())


if __name__ == "__main__":
    main()
