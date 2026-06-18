"""Train BARTpho-syllable (seq2seq): text → cây JSON (DESIGN.md §3, Phase 5).

    uv run --extra train python -m ontchatbot.scripts.train [--model ...] [--epochs ...]

Học cặp (câu → cây JSON) ở ``resources/datasets/{train,test}.jsonl`` (mỗi dòng có ``text``
+ ``tree``). Source = ``preprocess.clean(text)`` — **CÙNG hàm** pipeline gọi lúc infer (tránh
lệch phân phối train↔infer, GIAI_THUAT §4). Target = cây JSON nén (``json.dumps`` compact) để
model học sinh đúng chuỗi mà ``tree.parse`` đọc lại được.

Mixed precision **bf16** + optimizer **adamw_8bit** (bitsandbytes; vừa 6GB VRAM). Người dùng
chốt: batch 8, lr 3e-5, lr_scheduler cosine + warmup 100. Mặc định
nạp ``config.MODEL_NAME`` (bartpho-syllable large ~400M); muốn nhẹ VRAM hơn truyền
``--model vinai/bartpho-syllable-base``. ``--grad-checkpointing`` để giảm activation khi VRAM sát.

Eval ĐÚNG-CẠNH (sinh cây → traverse → so node với gold) tách ở ``evaluate.py`` — script này lo
train + lưu model; ở đây chỉ theo dõi eval-loss.
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
)

from ..config import (
    BATCH_SIZE,
    EPOCHS,
    LEARNING_RATE,
    MAX_SOURCE_LENGTH,
    MAX_TARGET_LENGTH,
    MODEL_DIR,
    MODEL_NAME,
    SEED,
    TEST_PATH,
    TRAIN_PATH,
)
from ..preprocess import clean

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
            tgt.append(json.dumps(d["tree"], ensure_ascii=False, separators=(",", ":")))
    return Dataset.from_dict({"source": src, "target": tgt})


def _tokenize(batch, tokenizer):
    """source → input_ids; target (JSON cây) → labels."""
    enc = tokenizer(batch["source"], max_length=MAX_SOURCE_LENGTH, truncation=True)
    enc["labels"] = tokenizer(text_target=batch["target"],
                              max_length=MAX_TARGET_LENGTH, truncation=True)["input_ids"]
    return enc


def train(args: argparse.Namespace) -> None:
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
    if args.grad_checkpointing:
        model.config.use_cache = False          # bắt buộc khi bật gradient checkpointing

    train_ds = _load_pairs(TRAIN_PATH).map(
        lambda b: _tokenize(b, tokenizer), batched=True, remove_columns=["source", "target"])
    eval_ds = _load_pairs(TEST_PATH).map(
        lambda b: _tokenize(b, tokenizer), batched=True, remove_columns=["source", "target"])

    targs = Seq2SeqTrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        bf16=True,                               # mixed precision bf16
        optim="adamw_8bit",                      # fused AdamW (CUDA)
        gradient_checkpointing=args.grad_checkpointing,
        warmup_steps=100,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=1,
        logging_steps=100,
        seed=args.seed,
        report_to="none",
        predict_with_generate=False,             # eval đúng-cạnh ở evaluate.py
    )

    collator = DataCollatorForSeq2Seq(tokenizer, model=model)
    trainer = Seq2SeqTrainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
        processing_class=tokenizer,
    )

    trainer.train()
    trainer.save_model(str(args.output_dir))     # lưu cả model + tokenizer
    tokenizer.save_pretrained(str(args.output_dir))
    print(f"[train] saved fine-tuned model → {args.output_dir}")
    print(f"[train] model={args.model} epochs={args.epochs} "
          f"batch={args.batch_size}x{args.grad_accum} bf16=True optim=adamw_8bit")


def main() -> None:
    p = argparse.ArgumentParser(description="Train BARTpho seq2seq: text → cây JSON")
    p.add_argument("--model", default=MODEL_NAME,
                   help="HF model id (mặc định bartpho-syllable; --model vinai/bartpho-syllable-base cho nhẹ)")
    p.add_argument("--epochs", type=float, default=EPOCHS)
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    p.add_argument("--grad-accum", type=int, default=1)
    p.add_argument("--lr", type=float, default=LEARNING_RATE)
    p.add_argument("--output-dir", default=MODEL_DIR, type=str)
    p.add_argument("--grad-checkpointing", action="store_true",
                   help="bật gradient checkpointing (giảm activation khi VRAM sát)")
    p.add_argument("--seed", type=int, default=SEED)
    train(p.parse_args())


if __name__ == "__main__":
    main()
