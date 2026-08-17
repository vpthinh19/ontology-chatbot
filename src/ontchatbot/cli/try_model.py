#!/usr/bin/env python
"""Gõ câu hỏi, xem truy vấn do model sinh và kết quả từ đồ thị.

    python -m ontchatbot.cli.try_model --seq2seq-lora  artifacts/run-<mốc>/model/t5gemma2/checkpoint-<n>
    python -m ontchatbot.cli.try_model --seq2seq-model artifacts/run-<mốc>/model/t5gemma2/model
    python -m ontchatbot.cli.try_model --adapter artifacts/run-<mốc>/adapter
    python -m ontchatbot.cli.try_model --seq2seq-lora <...> --hoi "học phí k67 bao nhiêu"

``--seq2seq-lora`` nạp LoRA lên model gốc; ``--seq2seq-model`` đọc model đã gộp.
Không có cờ nào thì chạy model gốc chưa tinh chỉnh.

Script chuẩn hóa câu hỏi, sinh SPARQL, kiểm tra truy vấn thuộc danh mục, chạy
trên ontology và in dữ kiện trả về.
"""

from __future__ import annotations

import argparse
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument("--seq2seq-model", type=Path, default=None)
    parser.add_argument(
        "--seq2seq-lora",
        type=Path,
        default=None,
        help="thư mục checkpoint LoRA seq2seq; nền nạp từ cache theo bản đã ghim",
    )
    parser.add_argument("--hoi", default=None, help="hỏi một câu rồi thoát")
    args = parser.parse_args()

    from ontchatbot.cli import benchmark_model as bench
    from ontchatbot.runtime.llm import (
        FineTunedQueryGenerator,
        LLMQueryGenerator,
        load_examples,
    )
    from ontchatbot.runtime.sparql import load_ontology
    from ontchatbot.settings import DATASET_DIR

    print("đang nạp model...", flush=True)
    if args.seq2seq_lora:
        generator = bench._seq2seq_adapter_generator(args.seq2seq_lora, 1)
        which = f"seq2seq LoRA {args.seq2seq_lora}"
    elif args.seq2seq_model:
        generator = bench._seq2seq_generator(args.seq2seq_model, 1)
        which = f"seq2seq đã gộp {args.seq2seq_model}"
    else:
        precision = bench.base_precision_for_adapter(args.adapter, "match-adapter")
        complete, complete_batch = bench.build_complete(
            bench.MODEL_ID, 200, "", precision == "4bit", False, args.adapter, 1
        )
        if args.adapter:
            generator = FineTunedQueryGenerator(complete, complete_batch=complete_batch)
            which = f"adapter {args.adapter} (nền {precision})"
        else:
            generator = LLMQueryGenerator(
                complete,
                load_examples(DATASET_DIR / "train.jsonl"),
                complete_batch=complete_batch,
            )
            which = "model GỐC chưa tinh chỉnh"

    graph = load_ontology()
    print(f"sẵn sàng · {which}\n")

    def answer(question: str) -> None:
        query = generator.generate(question)
        print(f"\n  truy vấn: {query[:300]}")
        if query.strip().casefold().startswith("không có thông tin"):
            print("  → model TỪ CHỐI trả lời")
            return
        try:
            rows = list(graph.query(query))
        except Exception as exc:  # Truy vấn không hợp lệ được hiển thị như một kết quả.
            print(f"  → truy vấn KHÔNG CHẠY ĐƯỢC: {type(exc).__name__}: {exc}")
            return
        if not rows:
            print("  → chạy được nhưng KHÔNG có dòng nào trả về")
            return
        print(f"  → {len(rows)} dòng:")
        for row in rows[:12]:
            print("     " + " | ".join("" if v is None else str(v)[:70] for v in row))
        if len(rows) > 12:
            print(f"     ... còn {len(rows) - 12} dòng")

    if args.hoi:
        answer(args.hoi)
        return

    print("Gõ câu hỏi rồi Enter. Ctrl-D hoặc dòng trống để thoát.\n")
    while True:
        try:
            question = input("hỏi> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            return
        answer(question)
        print()


if __name__ == "__main__":
    main()
