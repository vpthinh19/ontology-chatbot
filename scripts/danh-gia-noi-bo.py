#!/usr/bin/env python
"""Chấm model trên 15 CÂU NGƯỜI THẬT. NỘI BỘ - không đưa ra ngoài.

Đây là dữ liệu duy nhất trong dự án do người thật gõ: chín câu thu từ các phiên
thử trước (hai trong đó do giảng viên hướng dẫn test), sáu câu lấy từ
``test_llm.log`` - phiên chủ dự án gõ tay thử model huấn luyện trên dataset CŨ,
model đó trả lời SAI CẢ SÁU. Nhãn do chủ dự án tự xác nhận từng câu.

Vì sao tách khỏi bộ chấm chính: 15 câu này KHÔNG thuộc train/val/test. Báo cáo
benchmark chỉ được đo trên đúng ba tập đó, còn đây là phép thử riêng để hai
người trong dự án biết model làm được gì với câu người thật gõ vào.

    python scripts/danh-gia-noi-bo.py --adapter artifacts/run-.../adapter
    python scripts/danh-gia-noi-bo.py --seq2seq-model artifacts/seq2seq-.../model
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ontchatbot.research.benchmark import load_user_query_expectations
from ontchatbot.research.evaluation import evaluate_query_id_expectations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument("--seq2seq-model", type=Path, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    from ontchatbot.cli import benchmark_llm as bench
    from ontchatbot.runtime.llm import (
        FineTunedQueryGenerator,
        LLMQueryGenerator,
        load_examples,
    )
    from ontchatbot.settings import DATASET_DIR

    if args.seq2seq_model:
        generator = bench._seq2seq_generator(args.seq2seq_model, args.batch_size)
    else:
        model_id = args.model or bench.MODEL_ID
        precision = bench.base_precision_for_adapter(args.adapter, "match-adapter")
        complete, complete_batch = bench.build_complete(
            model_id, 200, "", precision == "4bit", False, args.adapter, args.batch_size
        )
        generator = (
            FineTunedQueryGenerator(complete, complete_batch=complete_batch)
            if args.adapter
            else LLMQueryGenerator(
                complete,
                load_examples(DATASET_DIR / "train.jsonl"),
                complete_batch=complete_batch,
            )
        )

    expectations = load_user_query_expectations()
    predictions = generator.generate_many(
        [item["question"] for item in expectations]
    )
    report = evaluate_query_id_expectations(
        expectations, predictions, include_cases=True
    )

    print(f"\n15 câu người thật: {report['correct']}/{report['count']} "
          f"({report['query_id_accuracy']:.1%})\n")
    for case in report["cases"]:
        print(("  ĐÚNG  " if case["correct"] else "  SAI   ") + case["question"][:64])
        if not case["correct"]:
            print(f"          chờ {case['expected_query_id']} · ra {case['predicted_query_id']}")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("\nkết quả:", args.output)


if __name__ == "__main__":
    main()
