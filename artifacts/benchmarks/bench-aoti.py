#!/usr/bin/env python3
"""Build và đo AOTInductor cho encoder của đúng benchmark bench-torch.py.

Mặc định chạy một lệnh: build package nếu chưa có, sau đó exec lại tiến trình
để phép đo load package/lần gọi đầu không thừa hưởng trạng thái lúc biên dịch.
Full generate không export được vì vòng tự hồi quy và EncoderDecoderCache thay
đổi; encoder là graph AOTI, decoder + KV cache tiếp tục chạy eager.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import statistics
import sys
import sysconfig
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / "artifacts/benchmarks"
AOTI_DIR = ROOT / "artifacts/benchmarks/aoti"
PACKAGE = AOTI_DIR / "t5gemma2-encoder-bf16.pt2"
BUILD_META = AOTI_DIR / "t5gemma2-encoder-bf16.build.json"
OUTPUT = RUN_DIR / "results-aoti.json"
REPORT = RUN_DIR / "report-aoti.md"
BASELINE_RUNNER = RUN_DIR / "bench-torch.py"


def configure_cuda_library_path() -> None:
    site_packages = Path(sysconfig.get_paths()["purelib"])
    candidates = (
        site_packages / "nvidia/cublas/lib",
        site_packages / "nvidia/cudnn/lib",
    )
    parts = [str(path) for path in candidates if path.is_dir()]
    parts.extend(filter(None, os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)))
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(dict.fromkeys(parts))


def load_baseline_runner():
    """Import runner cũ để tái dùng model, dữ liệu, generate và phép thống kê."""
    spec = importlib.util.spec_from_file_location("bench_torch_baseline", BASELINE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Không import được {BASELINE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


configure_cuda_library_path()
BASE = load_baseline_runner()
# bench-torch.py cũng bảo đảm hai thư viện này; khử trùng sau khi tái sử dụng nó.
configure_cuda_library_path()
torch = BASE.torch
from transformers import AutoTokenizer  # noqa: E402
from transformers.modeling_outputs import BaseModelOutput  # noqa: E402


class EncoderAOTIExport(torch.nn.Module):
    """Graph tensor-only: encoder chữ; không kéo vision tower vào package."""

    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, input_ids, attention_mask):
        return self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
            return_dict=False,
        )[0]


class LoadedAOTIEncoder(torch.nn.Module):
    """Cầu nối output tensor AOTI sang BaseModelOutput mà generate cần."""

    main_input_name = "input_ids"

    def __init__(self, compiled):
        super().__init__()
        self.compiled = compiled

    def forward(self, input_ids=None, attention_mask=None, **_kwargs):
        if input_ids is None:
            raise ValueError("AOTI encoder cần input_ids")
        if attention_mask is None:
            attention_mask = torch.ones_like(input_ids)
        hidden = self.compiled(input_ids, attention_mask)
        if isinstance(hidden, (tuple, list)):
            hidden = hidden[0]
        return BaseModelOutput(last_hidden_state=hidden)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_sizes(path: Path) -> dict:
    result = {
        "package_path": str(path.relative_to(ROOT)),
        "package_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "embedded_so_count": 0,
        "embedded_so_uncompressed_bytes": 0,
        "embedded_so_files": [],
    }
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            shared = [item for item in archive.infolist() if item.filename.endswith(".so")]
        result["embedded_so_count"] = len(shared)
        result["embedded_so_uncompressed_bytes"] = sum(item.file_size for item in shared)
        result["embedded_so_files"] = [
            {"name": item.filename, "bytes": item.file_size} for item in shared
        ]
    return result


def environment() -> dict:
    unavailable = BASE.cuda_unavailable_reason()
    return {
        "recorded_at": utc_now(),
        "python": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "transformers_version": importlib.metadata.version("transformers"),
        "cuda_build_version": torch.version.cuda,
        "cuda_available": unavailable is None,
        "cuda_unavailable_reason": unavailable,
        "cuda_device": torch.cuda.get_device_name(0) if unavailable is None else None,
        "ld_library_path": os.environ.get("LD_LIBRARY_PATH", ""),
    }


def initial_state(rows: list[dict]) -> dict:
    return {
        "status": "chưa đo được",
        "protocol": {
            "reused_runner": str(BASELINE_RUNNER.relative_to(ROOT)),
            "case_source": "artifacts/benchmarks/results-gpu.json configs[0].cases[].id",
            "case_ids": [row["id"] for row in rows],
            "model": str(BASE.MODEL_BF16.relative_to(ROOT)),
            "dtype": "bfloat16",
            "device": "cuda",
            "generation": {
                "do_sample": False,
                "num_beams": 1,
                "max_new_tokens": BASE.MAX_NEW_TOKENS,
                "batch_size": 1,
                "one_call_per_question": True,
                "warmup_calls": 1,
            },
            "aoti_scope": "text encoder only",
            "eager_scope": "autoregressive decoder, LM head, and dynamic KV cache",
            "dynamic_shapes": {
                "batch": 1,
                "encoder_sequence": {"min": 1, "max": 32768},
                "input_ids_and_attention_mask_share_dimension": True,
            },
            "p95": "nearest-rank",
        },
        "environment": environment(),
        "runtime_without_transformers": {
            "full_generation": False,
            "reason": "package chỉ chứa encoder; tokenizer, generate, decoder và EncoderDecoderCache còn dùng transformers",
        },
    }


def save_state(state: dict) -> None:
    OUTPUT.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(state)


def ns_ms(value) -> str:
    return "—" if value is None else f"{value / 1e6:,.0f}"


def ns_s(value) -> str:
    return "—" if value is None else f"{value / 1e9:,.1f}"


def mib(value) -> str:
    return "—" if value is None else f"{value / 2**20:,.1f}"


def write_report(state: dict) -> None:
    ok = state.get("status") == "ok"
    build = state.get("build", read_json(BUILD_META, {}) or {})
    artifact = state.get("artifact", build.get("artifact", {}))
    build_ns = build.get("build_excluding_model_load_ns")
    if ok:
        aoti = (
            f"{state['exact_target_matches']}/120 ({state['exact_target_rate']*100:.1f}%) | "
            f"{state['identical_to_torch_compile']}/120 | {ns_ms(state['latency_median_ns'])} | "
            f"{ns_ms(state['latency_p95_ns'])} | {ns_ms(state['package_load_ns'])} | "
            f"{ns_ms(state['first_call_ns'])} | {ns_s(build_ns)} | "
            f"{mib(artifact.get('embedded_so_uncompressed_bytes'))}"
        )
        cold_ns = state["package_load_ns"] + state["first_call_ns"]
        if cold_ns < 10_000_000_000:
            conclusion = "Cold-start nạp package + gọi đầu dưới 10 giây, bỏ được gần hết mốc 49 giây. "
        elif cold_ns < 39_200_000_000:
            conclusion = "Cold-start nạp package + gọi đầu giảm đáng kể so với 49 giây nhưng chưa biến mất. "
        else:
            conclusion = "Cold-start nạp package + gọi đầu không giảm đủ so với 49 giây. "
        if state["identical_to_torch_compile"] < 118:
            conclusion += "Độ lệch output quá lớn nên chưa thể dùng."
        elif state["latency_median_ns"] <= 900_000_000:
            conclusion += "Tốc độ và chất lượng đủ gần torch.compile."
        else:
            conclusion += "Chất lượng giữ được nhưng decoder eager làm mất lợi thế 784 ms."
    else:
        aoti = f"chưa đo | — | — | — | — | — | {ns_s(build_ns)} | {mib(artifact.get('embedded_so_uncompressed_bytes'))}"
        reason = state.get("error") or state.get("environment", {}).get("cuda_unavailable_reason") or "chưa chạy trên GPU"
        conclusion = f"Chưa thể kết luận vì sandbox không có GPU: {reason}"

    lines = [
        "# AOTInductor: T5Gemma2 bfloat16",
        "",
        "120 câu đúng ID lượt trước; greedy, batch 1, 320 token tối đa; warm-up tách khỏi 120 lần đo; p95 nearest-rank.",
        "",
        "| cấu hình | đúng target | giống torch compile | median ms | p95 ms | nạp .so ms | gọi đầu ms | build .so s | .so MiB |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        "| CT2 cpu int8 | 99/120 (82,5%) | — | 1.741 | — | — | — | — | — |",
        "| torch compile | 99/120 (82,5%) | 120/120 | 784 | 878 | — | 48.968 | — | — |",
        f"| AOTInductor (encoder) | {aoti} |",
        "",
        "## Phạm vi AOTI",
        "",
        "Chỉ text encoder là graph AOTI với chiều dài động 1–32768; decoder tự hồi quy, LM head và KV cache động còn eager. Build là export + compile/package, không gồm nạp model.",
        "Không chạy full generation nếu bỏ `transformers`; package `.pt2` chứa `.so` encoder nhưng runtime vẫn cần tokenizer, `generate` và cache của thư viện.",
        "",
        "## Kết luận",
        "",
        conclusion,
        "Khuyến nghị: chỉ thay torch.compile nếu lượt GPU cho ≥118/120 output giống hệt, median không quá 900 ms và gọi đầu giảm rõ rệt; nếu không, giữ cấu hình hiện tại.",
        "",
        "## Điểm yếu",
        "",
        "Mỗi câu đo một lần, một thứ tự và một máy; package phụ thuộc Torch/CUDA cùng ABI. Vì decoder chưa AOTI, phép đo này chỉ đánh giá phương án lai và không chứng minh full AOTI.",
    ]
    if len(lines) >= 35:
        raise AssertionError(f"Báo cáo có {len(lines)} dòng, phải dưới 35")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_package(rows: list[dict], force: bool) -> dict:
    AOTI_DIR.mkdir(parents=True, exist_ok=True)
    if PACKAGE.exists() and not force:
        metadata = read_json(BUILD_META, {}) or {}
        metadata["artifact"] = artifact_sizes(PACKAGE)
        return metadata

    tokenizer = AutoTokenizer.from_pretrained(BASE.MODEL_BF16, local_files_only=True)
    load_started = time.perf_counter_ns()
    model, model_source = BASE.load_model(torch.bfloat16, "cuda")
    BASE.synchronize("cuda")
    model_load_ns = time.perf_counter_ns() - load_started

    example_row = max(rows, key=lambda row: len(tokenizer(row["input"]).input_ids))
    example = tokenizer(example_row["input"], return_tensors="pt")
    input_ids = example["input_ids"].to("cuda")
    attention_mask = example["attention_mask"].to("cuda")
    wrapper = EncoderAOTIExport(model.get_encoder()).eval()
    sequence = torch.export.Dim("encoder_sequence", min=1, max=32768)

    export_started = time.perf_counter_ns()
    exported = torch.export.export(
        wrapper,
        (input_ids, attention_mask),
        dynamic_shapes={
            "input_ids": {1: sequence},
            "attention_mask": {1: sequence},
        },
        strict=False,
    )
    export_ns = time.perf_counter_ns() - export_started

    temporary = AOTI_DIR / ".t5gemma2-encoder-bf16.tmp.pt2"
    if temporary.exists():
        temporary.unlink()
    compile_started = time.perf_counter_ns()
    generated = Path(
        torch._inductor.aoti_compile_and_package(exported, package_path=temporary)
    )
    compile_package_ns = time.perf_counter_ns() - compile_started
    if generated.resolve() != temporary.resolve():
        raise RuntimeError(f"AOTI trả package ngoài đường dẫn yêu cầu: {generated}")
    os.replace(temporary, PACKAGE)

    metadata = {
        "status": "ok",
        "built_at": utc_now(),
        "torch_version": torch.__version__,
        "cuda_build_version": torch.version.cuda,
        "cuda_device": torch.cuda.get_device_name(0),
        "model_source": model_source,
        "example_case_id": example_row["id"],
        "example_encoder_tokens": input_ids.shape[1],
        "model_load_ns": model_load_ns,
        "export_ns": export_ns,
        "compile_package_ns": compile_package_ns,
        "build_excluding_model_load_ns": export_ns + compile_package_ns,
        "artifact": artifact_sizes(PACKAGE),
    }
    BUILD_META.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    del exported, wrapper, model, tokenizer
    gc.collect()
    torch.cuda.empty_cache()
    return metadata


def run_benchmark(rows: list[dict], cpu_int8: dict[str, str], build: dict) -> dict:
    reference_doc = read_json(BASE.OUTPUT)
    reference_config = next(
        item for item in reference_doc["configs"] if item["name"] == "cuda-bfloat16-compile"
    )
    if reference_config.get("status") != "ok" or len(reference_config.get("cases", [])) != 120:
        raise ValueError("results-torch.json không có đủ 120 output cuda-bfloat16-compile")
    torch_compile = {case["id"]: case["prediction"] for case in reference_config["cases"]}

    BASE.synchronize("cuda")
    package_load_started = time.perf_counter_ns()
    compiled_encoder = torch._inductor.aoti_load_package(PACKAGE)
    BASE.synchronize("cuda")
    package_load_ns = time.perf_counter_ns() - package_load_started

    support_load_started = time.perf_counter_ns()
    tokenizer = AutoTokenizer.from_pretrained(BASE.MODEL_BF16, local_files_only=True)
    model, model_source = BASE.load_model(torch.bfloat16, "cuda")
    original_encoder = model.model.encoder
    model.model.encoder = LoadedAOTIEncoder(compiled_encoder)
    del original_encoder
    gc.collect()
    torch.cuda.empty_cache()
    BASE.synchronize("cuda")
    support_load_ns = time.perf_counter_ns() - support_load_started

    torch.cuda.reset_peak_memory_stats()
    first_prediction, first_call_ns = BASE.generate(model, tokenizer, rows[0]["input"], "cuda")

    cases = []
    for index, row in enumerate(rows, 1):
        prediction, latency_ns = BASE.generate(model, tokenizer, row["input"], "cuda")
        cases.append(
            {
                "id": row["id"],
                "prediction": prediction,
                "latency_ns": latency_ns,
                "matches_target": prediction == row["target"],
                "matches_torch_compile": prediction == torch_compile[row["id"]],
                "matches_ct2_cpu_int8": prediction == cpu_int8[row["id"]],
            }
        )
        if index % 10 == 0:
            print(f"AOTInductor encoder + eager decoder: {index}/{len(rows)}", flush=True)

    latencies = [case["latency_ns"] for case in cases]
    exact = sum(case["matches_target"] for case in cases)
    result = initial_state(rows)
    result.update(
        {
            "status": "ok",
            "finished_at": utc_now(),
            "model_source": model_source,
            "build": build,
            "artifact": artifact_sizes(PACKAGE),
            "package_load_ns": package_load_ns,
            "support_model_and_tokenizer_load_ns": support_load_ns,
            "first_call_ns": first_call_ns,
            "first_call_prediction": first_prediction,
            "warmup_calls": 1,
            "measured_calls": len(cases),
            "exact_target_matches": exact,
            "exact_target_rate": exact / len(cases),
            "identical_to_torch_compile": sum(case["matches_torch_compile"] for case in cases),
            "identical_to_ct2_cpu_int8": sum(case["matches_ct2_cpu_int8"] for case in cases),
            "latency_median_ns": int(statistics.median(latencies)),
            "latency_p95_ns": BASE.percentile_nearest_rank(latencies, 0.95),
            "peak_vram_bytes": torch.cuda.max_memory_allocated(),
            "cases": cases,
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("all", "build", "run"), default="all")
    parser.add_argument("--force-build", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, cpu_int8, _gpu_fp32 = BASE.load_inputs()
    if len(rows) != 120:
        raise ValueError(f"Cần đúng 120 câu, nhận {len(rows)}")

    unavailable = BASE.cuda_unavailable_reason()
    if unavailable:
        previous = read_json(OUTPUT)
        if previous and previous.get("status") == "ok":
            previous.setdefault("unavailable_attempts", []).append(
                {"at": utc_now(), "reason": unavailable}
            )
            save_state(previous)
        else:
            state = initial_state(rows)
            state["error"] = unavailable
            if BUILD_META.exists():
                state["build"] = read_json(BUILD_META)
            save_state(state)
        print(f"chưa đo được: {unavailable}")
        print(f"đã ghi {OUTPUT}")
        print(f"đã ghi {REPORT}")
        return

    try:
        if args.mode in ("all", "build"):
            build = build_package(rows, args.force_build)
            state = initial_state(rows)
            state.update({"status": "đã build, chưa đo", "build": build, "artifact": build["artifact"]})
            save_state(state)
            print(f"đã build {PACKAGE}", flush=True)
            if args.mode == "build":
                return
            os.execv(sys.executable, [sys.executable, str(Path(__file__).resolve()), "--mode", "run"])

        if not PACKAGE.exists():
            raise FileNotFoundError(f"Chưa có package {PACKAGE}; chạy --mode build trước")
        build = read_json(BUILD_META, {}) or {}
        result = run_benchmark(rows, cpu_int8, build)
        save_state(result)
        print(f"đã ghi {OUTPUT}")
        print(f"đã ghi {REPORT}")
    except Exception as exc:
        state = initial_state(rows)
        state.update(
            {
                "status": "lỗi",
                "error": f"{type(exc).__name__}: {exc}",
                "build": read_json(BUILD_META, {}) or {},
            }
        )
        if PACKAGE.exists():
            state["artifact"] = artifact_sizes(PACKAGE)
        save_state(state)
        raise


if __name__ == "__main__":
    main()
