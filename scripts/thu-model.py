#!/usr/bin/env python
"""Gõ câu hỏi, xem model sinh truy vấn gì và đồ thị trả về gì. Chạy tại chỗ.

    python scripts/thu-model.py --adapter artifacts/run-<mốc>/adapter
    python scripts/thu-model.py --seq2seq-model artifacts/run-<mốc>/model
    python scripts/thu-model.py --adapter <...> --hoi "học phí k67 bao nhiêu"

Không có cờ nào thì chạy model GỐC chưa tinh chỉnh, để so.

Đây là đường ĐẦY ĐỦ: chuẩn hoá câu hỏi, sinh SPARQL, kiểm truy vấn có thuộc danh
mục không, chạy thật trên ontology, in dữ kiện trả về. Chấm điểm cho biết model
đúng bao nhiêu phần trăm; script này cho thấy nó SAI NHƯ THẾ NÀO, thứ mà một
con số không nói được.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument("--seq2seq-model", type=Path, default=None)
    parser.add_argument("--hoi", default=None, help="hỏi một câu rồi thoát")
    args = parser.parse_args()

    from ontchatbot.cli import benchmark_llm as bench
    from ontchatbot.runtime.llm import (
        FineTunedQueryGenerator,
        LLMQueryGenerator,
        load_examples,
    )
    from ontchatbot.runtime.sparql import load_ontology
    from ontchatbot.settings import DATASET_DIR

    print("đang nạp model...", flush=True)
    if args.seq2seq_model:
        generator = bench._seq2seq_generator(args.seq2seq_model, 1)
        which = f"seq2seq {args.seq2seq_model}"
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
        except Exception as exc:  # truy vấn hỏng cú pháp là một kết quả, không phải sự cố
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
