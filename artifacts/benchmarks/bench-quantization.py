"""Đo mọi kiểu tính toán của CTranslate2 trên một card, và trả lời câu hỏi
thật sự đáng tiền: gộp lô có làm đổi câu model viết ra không?

Bộ chấm là `evaluate_predictions` của chính dự án — cùng thước đã cho ra các con
số trong README. Cấu hình `cpu-int8` chạy đầu tiên làm phép thử chính bộ đo: nó
phải dựng lại đúng số của bài báo, nếu không thì lỗi nằm ở đây chứ không ở model.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import ctranslate2
from tokenizers import Tokenizer

from ontchatbot.research.evaluation import evaluate_predictions
from ontchatbot.runtime.model import MAX_SOURCE_LENGTH, MAX_TARGET_LENGTH
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.runtime.text import normalize_model_input

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "artifacts/serving-models/t5gemma2-f32"
DATASET = ROOT / "resources/dataset/test.jsonl"
OUTPUT = ROOT / "artifacts/benchmarks/results-quantization.json"

# Mỗi mục: tên, thiết bị, kiểu tính toán, các cỡ lô cần thử.
# Cỡ lô 4 là hình dạng thật của một lượt tra cứu: agent gửi 4 cụm từ khoá một lần.
PLAN = (
    ("cpu-int8", "cpu", "int8", (1,)),
    ("gpu-float32", "cuda", "float32", (1, 4, 16)),
    ("gpu-bfloat16", "cuda", "bfloat16", (1, 4)),
    ("gpu-float16", "cuda", "float16", (1, 4)),
    ("gpu-int8_float32", "cuda", "int8_float32", (1, 4)),
    ("gpu-int8_bfloat16", "cuda", "int8_bfloat16", (1,)),
    ("gpu-int8_float16", "cuda", "int8_float16", (1,)),
)


def load_rows() -> list[dict[str, str]]:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    return sorted(rows, key=lambda row: row["id"])


def load_engine(device: str, compute_type: str):
    tokenizer = Tokenizer.from_file(str(MODEL / "tokenizer.json"))
    tokenizer.no_padding()
    tokenizer.enable_truncation(max_length=MAX_SOURCE_LENGTH)
    translator = ctranslate2.Translator(
        str(MODEL), device=device, compute_type=compute_type
    )
    return translator, tokenizer


def decode(tokenizer, result) -> str:
    """Giống hệt bản trong runtime: mọi token phải nằm trong từ điển."""

    target_ids = []
    for token in result.hypotheses[0]:
        token_id = tokenizer.token_to_id(token)
        if token_id is None:
            return ""  # ngoài từ điển; bộ chấm tính là câu hỏng
        target_ids.append(token_id)
    return tokenizer.decode(target_ids, skip_special_tokens=True).strip()


def run(translator, tokenizer, texts: list[str], batch_size: int):
    """Sinh cho cả bộ, chia thành từng lô đúng cỡ, bấm giờ từng lô."""

    predictions: list[str] = []
    group_ms: list[float] = []
    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        tokens = [
            tokenizer.encode(normalize_model_input(text), add_special_tokens=True).tokens
            for text in chunk
        ]
        began = time.perf_counter()
        results = translator.translate_batch(
            tokens,
            beam_size=1,
            max_decoding_length=MAX_TARGET_LENGTH,
            max_batch_size=batch_size,
        )
        group_ms.append((time.perf_counter() - began) * 1000)
        predictions.extend(decode(tokenizer, result) for result in results)
    return predictions, group_ms


def run_one(name: str, device: str, compute_type: str, batch_size: int) -> None:
    """Đo đúng một cấu hình rồi ghi ra tệp riêng. Chạy trong tiến trình con để
    một cấu hình làm sập card không kéo đổ cả lượt đo."""

    rows = load_rows()
    texts = [row["input"] for row in rows]
    translator, tokenizer = load_engine(device, compute_type)
    run(translator, tokenizer, texts[:2], 1)  # khởi động nóng, không tính giờ

    began = time.perf_counter()
    predictions, group_ms = run(translator, tokenizer, texts, batch_size)
    wall = time.perf_counter() - began

    graph = load_ontology()
    scored = evaluate_predictions(rows, predictions, graph)
    key = f"{name}/lo-{batch_size}"
    payload = {
        "key": key,
        "device": device,
        "compute_type": compute_type,
        "batch_size": batch_size,
        "primary_metrics": scored["primary_metrics"],
        "error_counts": scored["error_counts"],
        "wall_seconds": round(wall, 2),
        "per_question_ms_median": round(statistics.median(group_ms) / batch_size, 1),
        "per_group_ms_median": round(statistics.median(group_ms), 1),
        "per_group_ms_p95": round(sorted(group_ms)[int(len(group_ms) * 0.95)], 1),
        "predictions": predictions,
    }
    out = OUTPUT.parent / f"quantization-{name}-lo{batch_size}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rates = {k: round(v["rate"] * 100, 1) for k, v in scored["primary_metrics"].items()}
    print(f"{key}: {rates} · {wall:.0f}s · mỗi lô {statistics.median(group_ms):.0f} ms", flush=True)


def gather() -> None:
    """Gộp các tệp rời thành một báo cáo, kèm hai phép so quan trọng."""

    rows = load_rows()
    runs, predictions_by_run = {}, {}
    for path in sorted(OUTPUT.parent.glob("quantization-*-lo*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        predictions_by_run[payload["key"]] = payload.pop("predictions")
        runs[payload["key"]] = payload

    batching = {}
    for key, preds in predictions_by_run.items():
        name, _, lot = key.partition("/lo-")
        if lot == "1":
            continue
        base = predictions_by_run.get(f"{name}/lo-1")
        if base is None:
            continue
        batching[key] = {
            "so_voi": f"{name}/lo-1",
            "giống": sum(a == b for a, b in zip(base, preds)),
            "tổng": len(base),
            "khác": [
                {"id": rows[i]["id"], "hoi": rows[i]["input"], "lo1": base[i], "lo_lon": preds[i]}
                for i in range(len(base))
                if base[i] != preds[i]
            ],
        }

    baseline = predictions_by_run.get("cpu-int8/lo-1")
    agreement = (
        {key: sum(a == b for a, b in zip(baseline, preds)) for key, preds in predictions_by_run.items()}
        if baseline
        else {}
    )
    report = {
        "model": str(MODEL.relative_to(ROOT)),
        "records": len(rows),
        "scorer": "ontchatbot.research.evaluation.evaluate_predictions",
        "runs": runs,
        "batching_agreement": batching,
        "agreement_with_cpu_int8": agreement,
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nđã gộp {len(runs)} lượt đo vào {OUTPUT.relative_to(ROOT)}")


def main() -> None:
    import argparse
    import subprocess
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="chạy đúng một cấu hình: tên,thiết bị,kiểu,cỡ lô")
    parser.add_argument("--gather", action="store_true", help="gộp các tệp rời lại")
    args = parser.parse_args()

    if args.gather:
        gather()
        return
    if args.only:
        name, device, compute_type, batch_size = args.only.split(",")
        run_one(name, device, compute_type, int(batch_size))
        return

    for name, device, compute_type, batch_sizes in PLAN:
        for batch_size in batch_sizes:
            done = OUTPUT.parent / f"quantization-{name}-lo{batch_size}.json"
            if done.is_file():
                print(f"{name}/lo-{batch_size}: đã có, bỏ qua", flush=True)
                continue
            completed = subprocess.run(
                [sys.executable, __file__, "--only", f"{name},{device},{compute_type},{batch_size}"],
            )
            if completed.returncode != 0:
                print(
                    f"{name}/lo-{batch_size}: TIẾN TRÌNH CHẾT (mã {completed.returncode}) — bỏ qua cấu hình này",
                    flush=True,
                )
    gather()


if __name__ == "__main__":
    main()
