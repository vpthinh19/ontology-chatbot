"""Train BARTpho-syllable (seq2seq): text → cây JSON.

    uv run --extra train python -m ontchatbot.scripts.train [--model ...] [--epochs ...]

Học cặp (câu → cây JSON) ở ``resources/datasets/{train,test}.jsonl`` (mỗi dòng có ``text``
+ ``tree``). Source = ``preprocess.clean(text)`` - **CÙNG hàm** pipeline gọi lúc infer (tránh
lệch phân phối train↔infer). Target = ``tree.to_model_json`` (đổi ``entities``→``items``
+ **space-pad** quanh mọi `"`): tokenizer BARTpho tokenize chữ DÍNH dấu `"` rất tệ (nhãn tiếng Việt
vỡ vụn, "individual"→"al"); pad làm nó tokenize tự nhiên như pretrain; ``model.from_model_json`` đảo
ngược lúc infer để ``tree.parse`` đọc lại được.

Mixed precision **bf16** + optimizer **adamw_8bit** (bitsandbytes; vừa 6GB VRAM). Người dùng
chốt: batch 8, lr 3e-5, lr_scheduler cosine + warmup 100. Mặc định
nạp ``config.MODEL_NAME`` (bartpho-syllable large ~400M); muốn nhẹ VRAM hơn truyền
``--model vinai/bartpho-syllable-base``. ``--grad-checkpointing`` để giảm activation khi VRAM sát.

**Validation** tách TỪ train (``--val-size``, mặc định ``config.VAL_SIZE``) - ``test.jsonl`` KHÔNG
đụng tới ở script này (giữ sạch cho ``evaluate.py``, tránh chọn checkpoint theo test = rò rỉ).
``load_best_model_at_end`` lưu checkpoint TỐT NHẤT theo ``eval_loss`` trên VAL, không phải bước cuối.

Eval ĐÚNG-CẠNH (sinh cây → traverse → so node với gold) tách ở ``evaluate.py`` - script này lo
train + lưu model; ở đây chỉ theo dõi eval-loss (trên VAL).
"""

from __future__ import annotations

import os
os.environ["BNB_CUDA_VERSION"] = "130"

import argparse
import json
import sys

from datasets import Dataset
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    EarlyStoppingCallback
)
import torch

from ..config import (
    BATCH_SIZE,
    GRAD_ACCUM,
    EPOCHS,
    LEARNING_RATE,
    MAX_SOURCE_LENGTH,
    MAX_TARGET_LENGTH,
    MODEL_DIR,
    MODEL_NAME,
    SEED,
    TRAIN_LOG_PATH,
    TRAIN_PATH,
    VAL_SIZE,
)
from ..preprocess import clean
from ..tree import from_model_json, to_model_json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _load_pairs(path):
    """jsonl → Dataset PHẲNG {source, target}. Serialize cây thành CHUỖI ngay (tránh Arrow
    suy luận schema lồng-đệ-quy của ``children`` → lỗi/coerce). ``clean()`` = đồng bộ với infer."""
    src, tgt = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            src.append(clean(d["text"]))
            # target = tree.to_model_json (space-pad + entities→items): tokenizer BARTpho tokenize chữ
            # dính dấu `"` rất tệ; pad → tokenize tự nhiên. model.from_model_json đảo ngược lúc infer.
            tgt.append(to_model_json(d["tree"]))
    return Dataset.from_dict({"source": src, "target": tgt})


def _tokenize(batch, tokenizer):
    """source → input_ids; target (JSON cây) → labels."""
    enc = tokenizer(batch["source"], max_length=MAX_SOURCE_LENGTH, truncation=True)
    enc["labels"] = tokenizer(text_target=batch["target"], max_length=MAX_TARGET_LENGTH, truncation=True)["input_ids"]
    return enc


def _check_target_roundtrip(tokenizer) -> None:
    """TRIPWIRE: target phải SỐNG SÓT qua tokenizer - ``from_model_json`` của chuỗi SAU tokenizer phải
    == của chuỗi TRƯỚC tokenizer (đo mất-mát tokenizer THUẦN, độc lập việc nắn dấu/đổi key trong
    to_model_json). Nếu không, model học chuỗi SAI mà không ai biết (vụ "individual"→"al" âm thầm 11%
    suốt). Luôn IN tỉ lệ; CHẶN train nếu <95%. Bắt mọi hồi quy (đổi serialization, thêm nhãn, đổi tokenizer)."""
    bad, examples, n = 0, [], 0
    with open(TRAIN_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            s = to_model_json(json.loads(line)["tree"])
            back = tokenizer.decode(tokenizer.encode(s, add_special_tokens=False),
                                    skip_special_tokens=True)
            try:
                ok = from_model_json(back) == from_model_json(s)
            except Exception:                    # noqa: BLE001 - JSON hỏng cũng là không round-trip
                ok = False
            if not ok:
                bad += 1
                if len(examples) < 3:
                    examples.append((s, back))
    rate = (n - bad) / n if n else 1.0
    print(f"[train] target round-trip qua tokenizer: {n - bad}/{n} ({rate:.1%}); hỏng={bad}")
    for s, b in examples:
        print(f"        S: {s[:120]}\n        B: {b[:120]}")
    if rate < 0.95:
        raise SystemExit(
            f"[train]  {bad}/{n} target KHÔNG dựng lại đúng cây qua tokenizer - model sẽ học chuỗi SAI. "
            "Sửa serialization (tree.to_model_json) / nhãn trước khi train (xem S vs B ở trên).")


def train(args: argparse.Namespace) -> None:
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    _check_target_roundtrip(tokenizer)           # chặn train trên target hỏng
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model, attn_implementation="sdpa")
    if args.grad_checkpointing:
        model.config.use_cache = False          # bắt buộc khi bật gradient checkpointing

    # Tách VAL từ train (seeded, có shuffle). test.jsonl KHÔNG nạp ở đây - giữ sạch cho evaluate.py.
    split = _load_pairs(TRAIN_PATH).train_test_split(test_size=args.val_size, seed=args.seed, shuffle=True)
    train_ds = split["train"].map(
        lambda b: _tokenize(b, tokenizer), batched=True, remove_columns=["source", "target"])
    eval_ds = split["test"].map(
        lambda b: _tokenize(b, tokenizer), batched=True, remove_columns=["source", "target"])
    print(f"[train] split train={len(train_ds)} / val={len(eval_ds)} "
          f"(val_size={args.val_size}, seed={args.seed}); test.jsonl giữ nguyên cho evaluate.py")

    targs = Seq2SeqTrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        bf16=True,
        tf32=True,
        optim="adamw_8bit",
        weight_decay=0.005,
        torch_compile=True,
        torch_compile_backend="inductor",
        torch_compile_mode="default",
        gradient_checkpointing=args.grad_checkpointing,
        warmup_steps=0.05,
        eval_strategy="steps",
        eval_steps=500,
        save_strategy="steps",
        save_steps=500,
        save_total_limit=2,
        logging_strategy="steps",
        logging_steps=0.05,
        seed=args.seed,
        report_to="none",
        predict_with_generate=False,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
    )

    early_stopping = EarlyStoppingCallback(
        early_stopping_patience=5,
    )

    collator = DataCollatorForSeq2Seq(tokenizer, model=model, pad_to_multiple_of=8)
    trainer = Seq2SeqTrainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
        processing_class=tokenizer,
        callbacks=[early_stopping],
    )

    trainer.train()
    trainer.save_model(str(args.output_dir))     # lưu cả model + tokenizer
    tokenizer.save_pretrained(str(args.output_dir))
    
    TRAIN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRAIN_LOG_PATH.write_text(
        json.dumps(trainer.state.log_history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[train] saved BEST-on-val fine-tuned model → {args.output_dir}")
    print(f"[train] log_history → {TRAIN_LOG_PATH} (cho Hình 8 training_curve)")
    print(f"[train] model={args.model} epochs={args.epochs} "
          f"batch={args.batch_size}x{args.grad_accum} val_size={args.val_size} bf16=True optim=adamw_8bit")


def main() -> None:
    p = argparse.ArgumentParser(description="Train BARTpho seq2seq: text → cây JSON")
    p.add_argument("--model", default=MODEL_NAME,
                   help="HF model id (mặc định bartpho-syllable; --model vinai/bartpho-syllable-base cho nhẹ)")
    p.add_argument("--epochs", type=float, default=EPOCHS)
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    p.add_argument("--grad-accum", type=int, default=GRAD_ACCUM)
    p.add_argument("--lr", type=float, default=LEARNING_RATE)
    p.add_argument("--output-dir", default=MODEL_DIR, type=str)
    p.add_argument("--val-size", type=float, default=VAL_SIZE,
                   help="tỉ lệ tách VAL từ train (test.jsonl không đụng tới; mặc định config.VAL_SIZE)")
    p.add_argument("--grad-checkpointing", action="store_true",
                   help="bật gradient checkpointing (giảm activation khi VRAM sát)")
    p.add_argument("--seed", type=int, default=SEED)
    train(p.parse_args())


if __name__ == "__main__":
    main()
