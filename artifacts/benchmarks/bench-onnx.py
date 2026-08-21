#!/usr/bin/env python3
"""Greedy benchmark T5Gemma2 thuần tokenizers + NumPy + ONNX Runtime."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / "artifacts/benchmarks"
MODEL_DIR = ROOT / "artifacts/serving-models/merged-bf16"
ONNX_DIR = ROOT / "artifacts/benchmarks/onnx-export"
DATASET = ROOT / "resources/dataset/test.jsonl"
CT2_RESULTS = RUN_DIR / "results-gpu.json"
TORCH_RESULTS = RUN_DIR / "results-torch.json"
OUTPUT = RUN_DIR / "results-onnx.json"
MAX_NEW_TOKENS = 320
EOS_TOKEN_ID = 1
# T5Gemma2 dùng decoder BOS, không phải pad như T5 cổ điển. Đây là token đầu
# mà GenerationMixin chọn từ generation_config/model config.
DECODER_START_TOKEN_ID = 2


def percentile_nearest_rank(values: list[int], fraction: float) -> int:
    return sorted(values)[math.ceil(fraction * len(values)) - 1]


def distribution_bytes(name: str) -> dict | None:
    try:
        dist = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return None
    apparent = allocated = 0
    paths, inodes = set(), set()
    for entry in dist.files or ():
        path = Path(os.path.abspath(dist.locate_file(entry)))
        try:
            if path in paths or (not path.exists() and not path.is_symlink()):
                continue
            paths.add(path)
            stat = path.lstat()
        except OSError:
            continue
        inode = (stat.st_dev, stat.st_ino)
        if inode in inodes:
            continue
        inodes.add(inode)
        apparent += stat.st_size
        allocated += getattr(stat, "st_blocks", 0) * 512
    return {
        "name": dist.metadata["Name"], "version": dist.version,
        "files": len(inodes), "apparent_bytes": apparent, "allocated_bytes": allocated,
    }


def model_files() -> dict:
    files = sorted(path for path in ONNX_DIR.iterdir() if path.is_file() and (path.suffix == ".onnx" or ".onnx.data" in path.name))
    return {
        "files": [{"name": p.name, "bytes": p.stat().st_size} for p in files],
        "total_bytes": sum(p.stat().st_size for p in files),
        "onnx_only_bytes": sum(p.stat().st_size for p in files if p.suffix == ".onnx"),
    }


def load_rows() -> tuple[list[dict], dict[str, str]]:
    ct2 = json.loads(CT2_RESULTS.read_text(encoding="utf-8"))
    ids = [case["id"] for case in ct2["configs"][0]["cases"]]
    if len(ids) != 120 or len(set(ids)) != 120:
        raise ValueError(f"Cần đúng 120 ID duy nhất, nhận {len(ids)}")
    rows_by_id = {
        row["id"]: row
        for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()
        for row in (json.loads(line),)
    }
    torch_result = json.loads(TORCH_RESULTS.read_text(encoding="utf-8"))
    reference = next(c for c in torch_result["configs"] if c["name"] == "cuda-bfloat16-compile")
    if reference["status"] != "ok":
        raise ValueError("results-torch.json chưa có cuda-bfloat16-compile hợp lệ")
    reference_by_id = {case["id"]: case["prediction"] for case in reference["cases"]}
    return [rows_by_id[qid] for qid in ids], reference_by_id


class OnnxGenerator:
    def __init__(self, provider: str):
        self.tokenizer = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
        if provider == "CUDAExecutionProvider" and hasattr(ort, "preload_dlls"):
            # ORT không tự tìm các wheel nvidia-* trong site-packages trên Linux.
            # Chuỗi rỗng yêu cầu ORT tìm đúng thư mục chuẩn của các wheel đó.
            ort.preload_dlls(cuda=True, cudnn=True, msvc=False, directory="")
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = min(8, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        providers = [provider]
        self.encoder = ort.InferenceSession(str(ONNX_DIR / "encoder.onnx"), sess_options=options, providers=providers)
        self.decoder_init = ort.InferenceSession(str(ONNX_DIR / "decoder-init.onnx"), sess_options=options, providers=providers)
        self.decoder_cache = ort.InferenceSession(str(ONNX_DIR / "decoder-cache.onnx"), sess_options=options, providers=providers)
        for session in (self.encoder, self.decoder_init, self.decoder_cache):
            session.disable_fallback()
            if provider not in session.get_providers():
                raise RuntimeError(f"{provider} không hoạt động; providers={session.get_providers()}")
        self.provider = provider
        self.cache_graph_inputs = {x.name for x in self.decoder_cache.get_inputs()}
        self.cache_input_names = [x.name for x in self.decoder_cache.get_inputs() if x.name.startswith("past_")]
        self.cache_output_names = [x.name for x in self.decoder_cache.get_outputs() if x.name.startswith("present_self_")]

    def generate(self, text: str) -> tuple[str, int]:
        encoded = self.tokenizer.encode(text)
        input_ids = np.asarray([encoded.ids], dtype=np.int64)
        attention_mask = np.ones_like(input_ids)
        hidden = self.encoder.run(None, {"input_ids": input_ids, "attention_mask": attention_mask})[0]
        decoder_ids = np.asarray([[DECODER_START_TOKEN_ID]], dtype=np.int64)
        init = self.decoder_init.run(None, {
            "decoder_input_ids": decoder_ids,
            "encoder_attention_mask": attention_mask,
            "encoder_hidden_state": hidden,
        })
        next_id = int(np.argmax(init[0][0]))
        generated = [next_id]
        # decoder-init trả 36 self tensors rồi 36 cross tensors, đúng cùng thứ
        # tự tên đầu vào của decoder-cache.
        cache = {name: value for name, value in zip(self.cache_input_names, init[1:], strict=True)}
        while next_id != EOS_TOKEN_ID and len(generated) < MAX_NEW_TOKENS:
            feeds = {
                "decoder_input_ids": np.asarray([[next_id]], dtype=np.int64),
                "encoder_attention_mask": attention_mask,
                **cache,
            }
            # Cross K/V đã có trong cache nên tracer loại encoder hidden khỏi
            # graph cached; chỉ đưa tensor này nếu một bản xuất khác còn giữ nó.
            if "encoder_hidden_state" in self.cache_graph_inputs:
                feeds["encoder_hidden_state"] = hidden
            result = self.decoder_cache.run(None, feeds)
            next_id = int(np.argmax(result[0][0]))
            generated.append(next_id)
            for name, value in zip(self.cache_input_names[: len(self.cache_output_names)], result[1:], strict=True):
                cache[name] = value
        return self.tokenizer.decode(generated, skip_special_tokens=True), len(generated)


def benchmark(provider: str, rows: list[dict], reference: dict[str, str]) -> dict:
    common = {"name": "cuda-float32" if provider == "CUDAExecutionProvider" else "cpu-float32", "provider": provider}
    if provider not in ort.get_available_providers():
        return {**common, "status": "chưa đo được", "error": f"provider không có; available={ort.get_available_providers()}"}
    load_started = time.perf_counter_ns()
    try:
        generator = OnnxGenerator(provider)
    except Exception as exc:
        return {**common, "status": "chưa đo được", "load_ns": time.perf_counter_ns() - load_started, "error": f"{type(exc).__name__}: {exc}"}
    load_ns = time.perf_counter_ns() - load_started
    first_started = time.perf_counter_ns()
    try:
        generator.generate(rows[0]["input"])
    except Exception as exc:
        return {**common, "status": "warm-up lỗi", "load_ns": load_ns, "first_call_ns": time.perf_counter_ns() - first_started, "error": f"{type(exc).__name__}: {exc}"}
    first_call_ns = time.perf_counter_ns() - first_started
    cases = []
    for index, row in enumerate(rows, 1):
        started = time.perf_counter_ns()
        prediction, tokens = generator.generate(row["input"])
        elapsed = time.perf_counter_ns() - started
        cases.append({
            "id": row["id"], "prediction": prediction, "generated_tokens": tokens,
            "latency_ns": elapsed, "matches_target": prediction == row["target"],
            "matches_cuda_bfloat16_compile": prediction == reference[row["id"]],
        })
        if index % 10 == 0:
            print(f"{common['name']}: {index}/{len(rows)}", flush=True)
    latencies = [case["latency_ns"] for case in cases]
    return {
        **common, "status": "ok", "load_ns": load_ns, "first_call_ns": first_call_ns,
        "warmup_calls": 1, "measured_calls": len(cases),
        "exact_target_matches": sum(c["matches_target"] for c in cases),
        "exact_target_rate": sum(c["matches_target"] for c in cases) / len(cases),
        "identical_to_cuda_bfloat16_compile": sum(c["matches_cuda_bfloat16_compile"] for c in cases),
        "latency_median_ns": int(statistics.median(latencies)),
        "latency_p95_ns": percentile_nearest_rank(latencies, .95), "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", nargs="*", choices=["cpu", "cuda"], default=["cuda", "cpu"])
    args = parser.parse_args()
    rows, reference = load_rows()
    report = {
        "protocol": {"case_ids": [row["id"] for row in rows], "max_new_tokens": MAX_NEW_TOKENS, "greedy": True, "batch_size": 1, "warmup_calls": 1, "p95": "nearest-rank"},
        "environment": {"started_at": datetime.now(timezone.utc).isoformat(), "python": sys.version, "platform": platform.platform(), "cpu": platform.processor() or platform.machine(), "onnxruntime_version": ort.__version__, "available_providers": ort.get_available_providers()},
        "disk_usage": {"model": model_files(), "onnxruntime_gpu": distribution_bytes("onnxruntime-gpu"), "tokenizers": distribution_bytes("tokenizers"), "torch": distribution_bytes("torch"), "transformers": distribution_bytes("transformers"), "ctranslate2": distribution_bytes("ctranslate2")},
        "runtime_imports": {"script_imports_torch": False, "script_imports_transformers": False, "proof": "bench-onnx.py chỉ import numpy, onnxruntime và tokenizers; chạy benchmark không import torch/transformers"},
        "configs": [],
    }
    mapping = {"cuda": "CUDAExecutionProvider", "cpu": "CPUExecutionProvider"}
    for short in args.providers:
        print(f"Bắt đầu {short}", flush=True)
        report["configs"].append(benchmark(mapping[short], rows, reference))
        OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["environment"]["finished_at"] = datetime.now(timezone.utc).isoformat()
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Đã ghi {OUTPUT}")


if __name__ == "__main__":
    main()
