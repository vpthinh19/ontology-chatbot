"""Đo CTranslate2 theo từng câu trên cùng một mẫu test tất định."""

from __future__ import annotations

import gc
import json
import math
import os
import random
import statistics
import subprocess
import time
from pathlib import Path

import ctranslate2
from rdflib.plugins.sparql.parser import parseQuery

from ontchatbot.research.evaluation import _row_key
from ontchatbot.runtime.model import CTranslate2Generator
from ontchatbot.runtime.sparql import PREFIXES, execute_select, load_ontology


ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "artifacts/serving-models/t5gemma2-f32"
DATASET = ROOT / "resources/dataset/test.jsonl"
OUTPUT = ROOT / "artifacts/benchmarks/results-gpu.json"
SEED = 42
PER_REGISTER = 30
CONFIGS = (
    ("cpu-int8", "cpu", "int8"),
    ("cuda-bfloat16", "cuda", "bfloat16"),
    ("cuda-int8_bfloat16", "cuda", "int8_bfloat16"),
    ("cuda-float16", "cuda", "float16"),
    ("cuda-int8_float16", "cuda", "int8_float16"),
)


def select_rows() -> list[dict[str, str]]:
    rows = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
    ]
    rows = [row for row in rows if row["target"].lstrip().upper().startswith("SELECT")]
    selected: list[dict[str, str]] = []
    for register in ("formal", "neutral", "colloquial", "noisy"):
        group = sorted(
            (row for row in rows if row["register"] == register),
            key=lambda row: row["id"],
        )
        random.Random(f"{SEED}:{register}").shuffle(group)
        selected.extend(group[:PER_REGISTER])
    return sorted(selected, key=lambda row: row["id"])


def percentile_nearest_rank(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def process_vram_bytes() -> int | None:
    """Đọc VRAM của chính tiến trình; trả None nếu NVML/nvidia-smi không dùng được."""

    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            check=True,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    used_mib = 0
    found = False
    for line in completed.stdout.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) == 2 and fields[0] == str(os.getpid()):
            used_mib += int(fields[1])
            found = True
    return used_mib * 1024 * 1024 if found else 0


def parse_ok(query: str) -> bool:
    try:
        parseQuery(PREFIXES + query)
    except Exception:
        return False
    return True


def result_key(graph, query: str) -> list:
    if not parse_ok(query):
        return ["syntax-error"]
    try:
        rows = execute_select(graph, query)
    except Exception:
        return ["execution-error"]
    return ["rows", repr(_row_key(rows))]


def run_config(name: str, device: str, compute_type: str, rows, graph) -> dict:
    ctranslate2.set_random_seed(SEED)
    started = time.perf_counter_ns()
    try:
        generator = CTranslate2Generator.load(
            MODEL, device=device, compute_type=compute_type
        )
    except Exception as exc:
        return {
            "name": name,
            "device": device,
            "compute_type": compute_type,
            "status": "không nạp được",
            "load_error": f"{type(exc).__name__}: {exc}",
            "load_ns": time.perf_counter_ns() - started,
        }
    load_ns = time.perf_counter_ns() - started
    # Khởi động nóng giống nhau, nằm ngoài 120 lần gọi được tính thời gian.
    generator.generate(rows[0]["input"])
    peak_vram = process_vram_bytes() if device == "cuda" else None
    cases = []
    for index, row in enumerate(rows, start=1):
        before = time.perf_counter_ns()
        prediction = generator.generate(row["input"])
        latency_ns = time.perf_counter_ns() - before
        used = process_vram_bytes() if device == "cuda" else None
        if used is not None:
            peak_vram = max(peak_vram or 0, used)
        cases.append(
            {
                "id": row["id"],
                "register": row["register"],
                "prediction": prediction,
                "syntax_ok": parse_ok(prediction),
                "result_key": result_key(graph, prediction),
                "latency_ns": latency_ns,
            }
        )
        if index % 10 == 0:
            print(f"{name}: {index}/{len(rows)}", flush=True)
    latencies = [case["latency_ns"] for case in cases]
    return {
        "name": name,
        "device": device,
        "compute_type": compute_type,
        "status": "ok",
        "load_ns": load_ns,
        "warmup_calls": 1,
        "measured_calls": len(cases),
        "syntax_errors": sum(not case["syntax_ok"] for case in cases),
        "latency_median_ns": int(statistics.median(latencies)),
        "latency_p95_ns": percentile_nearest_rank(latencies, 0.95),
        "peak_process_vram_bytes": peak_vram,
        "cases": cases,
    }


def main() -> None:
    rows = select_rows()
    graph = load_ontology()
    report = {
        "protocol": {
            "seed": SEED,
            "selection": "30/register, shuffle tất định từng register rồi sắp theo id",
            "records": len(rows),
            "register_counts": {
                register: sum(row["register"] == register for row in rows)
                for register in ("formal", "neutral", "colloquial", "noisy")
            },
            "one_call_per_question": True,
            "batch_size": 1,
            "beam_size": 1,
            "max_decoding_length": 320,
            "warmup_calls_per_config": 1,
            "p95": "nearest-rank",
            "model": str(MODEL.relative_to(ROOT)),
            "ctranslate2_version": ctranslate2.__version__,
        },
        "configs": [],
    }
    for spec in CONFIGS:
        print(f"bắt đầu {spec[0]}", flush=True)
        result = run_config(*spec, rows, graph)
        report["configs"].append(result)
        OUTPUT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        gc.collect()

    baseline = report["configs"][0]
    if baseline["status"] != "ok":
        raise RuntimeError("cấu hình mốc cpu-int8 không chạy được")
    base_cases = {case["id"]: case for case in baseline["cases"]}
    for config in report["configs"]:
        if config["status"] != "ok":
            config["text_differences_vs_cpu_int8"] = None
            config["result_differences_vs_cpu_int8"] = None
            continue
        config["text_differences_vs_cpu_int8"] = sum(
            case["prediction"] != base_cases[case["id"]]["prediction"]
            for case in config["cases"]
        )
        config["result_differences_vs_cpu_int8"] = sum(
            case["result_key"] != base_cases[case["id"]]["result_key"]
            for case in config["cases"]
        )
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"đã ghi {OUTPUT}")


if __name__ == "__main__":
    main()
