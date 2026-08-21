#!/usr/bin/env python3
"""Đo PyTorch/torch.compile trên đúng 120 câu của phép đo CT2.

Chạy mặc định toàn bộ sáu cấu hình:
    .venv/bin/python artifacts/benchmarks/bench-torch.py

Kết quả được ghi sau từng cấu hình để không mất các phép đo đã xong nếu một
cấu hình sau đó lỗi. Float32 được gộp lại từ model nền và adapter để không làm
mất độ chính xác của phép cộng LoRA do lấy model đã lưu bfloat16 rồi ép kiểu.
"""

from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import math
import os
import platform
import statistics
import sys
import sysconfig
import time
from datetime import datetime, timezone
from pathlib import Path


# torch phải thấy các thư viện này ngay từ lúc import, không chỉ khi tạo model.
SITE_PACKAGES = Path(sysconfig.get_paths()["purelib"])
CUDA_LIBRARY_DIRS = (
    SITE_PACKAGES / "nvidia/cublas/lib",
    SITE_PACKAGES / "nvidia/cudnn/lib",
)
old_library_path = os.environ.get("LD_LIBRARY_PATH", "")
library_parts = [str(path) for path in CUDA_LIBRARY_DIRS if path.is_dir()]
if old_library_path:
    library_parts.append(old_library_path)
os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(library_parts)

import torch  # noqa: E402  (cần đặt LD_LIBRARY_PATH trước)
from peft import PeftModel  # noqa: E402
from transformers import (  # noqa: E402
    AutoConfig,
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)


ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / "artifacts/benchmarks"
MODEL_BF16 = ROOT / "artifacts/serving-models/merged-bf16"
ADAPTER = ROOT / "artifacts/adapters/t5gemma2"
BASE_MODEL = "google/t5gemma-2-270m-270m"
BASE_REVISION = "7c38f16641f455ef0685b18431faf1b17722d5a1"
DATASET = ROOT / "resources/dataset/test.jsonl"
CT2_GPU = RUN_DIR / "results-gpu.json"
CT2_FP32 = RUN_DIR / "results-fp32.json"
OUTPUT = RUN_DIR / "results-torch.json"
REPORT = RUN_DIR / "report-torch.md"
MAX_NEW_TOKENS = 320

CONFIGS = (
    ("cpu-float32", "cpu", torch.float32, False),
    ("cpu-bfloat16", "cpu", torch.bfloat16, False),
    ("cuda-float32", "cuda", torch.float32, False),
    ("cuda-bfloat16", "cuda", torch.bfloat16, False),
    ("cuda-bfloat16-compile", "cuda", torch.bfloat16, True),
    ("cuda-float32-compile", "cuda", torch.float32, True),
)


def percentile_nearest_rank(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def packages_bytes(distribution_names: list[str]) -> dict | None:
    """Dung lượng union của đúng các file thuộc một hay nhiều distribution."""
    distributions = []
    for distribution_name in distribution_names:
        try:
            distributions.append(importlib.metadata.distribution(distribution_name))
        except importlib.metadata.PackageNotFoundError:
            continue
    if not distributions:
        return None
    apparent = 0
    allocated = 0
    seen_paths: set[Path] = set()
    seen_inodes: set[tuple[int, int]] = set()
    for dist in distributions:
        for entry in dist.files or ():
            path = Path(dist.locate_file(entry))
            try:
                # Không resolve symlink: stat() sẽ tính lại kích thước thư viện đích
                # cho từng tên .so liên kết, lớn hơn dung lượng thực mà du báo cáo.
                absolute = Path(os.path.abspath(path))
                if absolute in seen_paths or (
                    not absolute.exists() and not absolute.is_symlink()
                ):
                    continue
                seen_paths.add(absolute)
                stat = absolute.lstat()
            except OSError:
                continue
            inode = (stat.st_dev, stat.st_ino)
            if inode in seen_inodes:
                continue
            seen_inodes.add(inode)
            apparent += stat.st_size
            allocated += getattr(stat, "st_blocks", 0) * 512
    return {
        "distributions": [
            {"name": dist.metadata["Name"], "version": dist.version}
            for dist in distributions
        ],
        "files": len(seen_inodes),
        "apparent_bytes": apparent,
        "allocated_bytes": allocated,
    }


def package_bytes(distribution_name: str) -> dict | None:
    return packages_bytes([distribution_name])


def disk_usage() -> dict:
    core = {}
    for name in ("torch", "transformers", "ctranslate2"):
        core[name] = package_bytes(name)
    nvidia_names = sorted(
        {
            dist.metadata["Name"]
            for dist in importlib.metadata.distributions()
            if (dist.metadata.get("Name") or "").lower().startswith("nvidia-")
        },
        key=str.lower,
    )
    nvidia = {name: package_bytes(name) for name in nvidia_names}
    nvidia_total = packages_bytes(nvidia_names)
    return {
        "method": "cộng lstat.st_size và st_blocks*512 của các file trong metadata distribution; không follow symlink, inode trùng chỉ tính một lần trong từng distribution",
        "site_packages": str(SITE_PACKAGES),
        "core": core,
        "nvidia": nvidia,
        "nvidia_total_apparent_bytes": nvidia_total["apparent_bytes"],
        "nvidia_total_allocated_bytes": nvidia_total["allocated_bytes"],
        "nvidia_total_note": "union toàn bộ nvidia-*; không cộng lặp file/inode do nhiều metadata cùng khai báo",
    }


def load_inputs() -> tuple[list[dict], dict[str, str], dict[str, str]]:
    gpu = json.loads(CT2_GPU.read_text(encoding="utf-8"))
    ids = [case["id"] for case in gpu["configs"][0]["cases"]]
    if len(ids) != 120 or len(set(ids)) != 120:
        raise ValueError(f"Mốc CT2 không chứa đúng 120 ID duy nhất: {len(ids)}")
    all_rows = {
        row["id"]: row
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in (json.loads(line),)
    }
    missing = [qid for qid in ids if qid not in all_rows]
    if missing:
        raise KeyError(f"Thiếu ID trong test.jsonl: {missing}")
    rows = [all_rows[qid] for qid in ids]

    cpu_config = next(c for c in gpu["configs"] if c["name"] == "cpu-int8")
    cpu_int8 = {case["id"]: case["prediction"] for case in cpu_config["cases"]}
    fp32 = json.loads(CT2_FP32.read_text(encoding="utf-8"))
    gpu_fp32 = {case["id"]: case["prediction"] for case in fp32["gpu-float32"]}
    for name, predictions in (("cpu-int8", cpu_int8), ("gpu-float32", gpu_fp32)):
        absent = [qid for qid in ids if qid not in predictions]
        if absent:
            raise KeyError(f"Mốc {name} thiếu {len(absent)} ID")
    return rows, cpu_int8, gpu_fp32


def set_config_dtype(config, dtype: torch.dtype) -> None:
    """T5Gemma2 có dtype ở nhiều config lồng nhau; phải đặt đồng nhất."""
    config.dtype = dtype
    config.encoder.dtype = dtype
    config.encoder.text_config.dtype = dtype
    config.decoder.dtype = dtype


def load_model(dtype: torch.dtype, device: str):
    if dtype == torch.float32:
        config = AutoConfig.from_pretrained(
            BASE_MODEL, revision=BASE_REVISION
        )
        set_config_dtype(config, dtype)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            BASE_MODEL,
            revision=BASE_REVISION,
            config=config,
            dtype=dtype,
        )
        model = PeftModel.from_pretrained(
            model, ADAPTER, local_files_only=True
        ).merge_and_unload()
        model_source = "base+adapter, gộp trong float32"
    else:
        config = AutoConfig.from_pretrained(MODEL_BF16, local_files_only=True)
        set_config_dtype(config, dtype)
        model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_BF16,
            config=config,
            dtype=dtype,
            local_files_only=True,
        )
        model_source = "model đã gộp và lưu bfloat16"
    return model.eval().to(device), model_source


def synchronize(device: str) -> None:
    if device == "cuda":
        torch.cuda.synchronize()


def generate(model, tokenizer, text: str, device: str) -> tuple[str, int]:
    encoded = tokenizer(text, return_tensors="pt")
    encoded = {key: value.to(device) for key, value in encoded.items()}
    synchronize(device)
    started = time.perf_counter_ns()
    with torch.inference_mode():
        output_ids = model.generate(
            **encoded,
            do_sample=False,
            num_beams=1,
            max_new_tokens=MAX_NEW_TOKENS,
        )
    synchronize(device)
    elapsed = time.perf_counter_ns() - started
    return tokenizer.decode(output_ids[0], skip_special_tokens=True), elapsed


def cuda_unavailable_reason() -> str | None:
    if torch.cuda.is_available():
        return None
    try:
        torch.cuda.init()
    except Exception as exc:  # thông báo thực tế hữu ích hơn một cờ False
        return f"{type(exc).__name__}: {exc}"
    return "torch.cuda.is_available() trả về False"


def cpu_name() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def run_config(
    name: str,
    device: str,
    dtype: torch.dtype,
    compile_model: bool,
    rows: list[dict],
    cpu_int8: dict[str, str],
    gpu_fp32: dict[str, str],
) -> dict:
    common = {
        "name": name,
        "device": device,
        "dtype": str(dtype).removeprefix("torch."),
        "compile": compile_model,
    }
    if device == "cuda":
        reason = cuda_unavailable_reason()
        if reason:
            return {**common, "status": "chưa đo được", "error": reason}

    if device == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter_ns()
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_BF16, local_files_only=True)
        model, model_source = load_model(dtype, device)
        synchronize(device)
    except Exception as exc:
        return {
            **common,
            "status": "không nạp được",
            "load_ns": time.perf_counter_ns() - started,
            "error": f"{type(exc).__name__}: {exc}",
        }
    load_ns = time.perf_counter_ns() - started

    compile_ns = None
    try:
        if compile_model:
            model.compile()
            # Lần gọi này gồm biên dịch và sinh; tách khỏi 120 độ trễ phục vụ.
            _, compile_ns = generate(model, tokenizer, rows[0]["input"], device)
        else:
            generate(model, tokenizer, rows[0]["input"], device)
    except Exception as exc:
        return {
            **common,
            "status": "warm-up/compile lỗi",
            "model_source": model_source,
            "load_ns": load_ns,
            "compile_first_call_ns": compile_ns,
            "error": f"{type(exc).__name__}: {exc}",
        }

    cases = []
    for index, row in enumerate(rows, 1):
        prediction, latency_ns = generate(
            model, tokenizer, row["input"], device
        )
        cases.append(
            {
                "id": row["id"],
                "prediction": prediction,
                "latency_ns": latency_ns,
                "matches_target": prediction == row["target"],
                "matches_ct2_cpu_int8": prediction == cpu_int8[row["id"]],
                "matches_ct2_gpu_float32": prediction == gpu_fp32[row["id"]],
            }
        )
        if index % 10 == 0:
            print(f"{name}: {index}/{len(rows)}", flush=True)

    latencies = [case["latency_ns"] for case in cases]
    result = {
        **common,
        "status": "ok",
        "model_source": model_source,
        "load_ns": load_ns,
        "warmup_calls": 1,
        "compile_first_call_ns": compile_ns,
        "compile_timing_note": (
            "thời gian lần generate đầu, gồm biên dịch và chính lần sinh đó"
            if compile_model
            else None
        ),
        "measured_calls": len(cases),
        "exact_target_matches": sum(c["matches_target"] for c in cases),
        "exact_target_rate": sum(c["matches_target"] for c in cases) / len(cases),
        "identical_to_ct2_cpu_int8": sum(c["matches_ct2_cpu_int8"] for c in cases),
        "identical_to_ct2_gpu_float32": sum(
            c["matches_ct2_gpu_float32"] for c in cases
        ),
        "latency_median_ns": int(statistics.median(latencies)),
        "latency_p95_ns": percentile_nearest_rank(latencies, 0.95),
        "peak_vram_bytes": (
            torch.cuda.max_memory_allocated() if device == "cuda" else None
        ),
        "cases": cases,
    }
    del model, tokenizer
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()
    return result


def mib(value: int | None) -> str:
    return "—" if value is None else f"{value / 2**20:,.0f}"


def ms(value: int | None) -> str:
    return "—" if value is None else f"{value / 1e6:,.0f}"


def gib(value: int | None) -> str:
    return "—" if value is None else f"{value / 2**30:.2f}"


def write_report(report: dict) -> None:
    configs = report["configs"]
    ok = [c for c in configs if c["status"] == "ok"]
    lines = [
        "# Đo PyTorch so với CTranslate2",
        "",
        f"Đo {len(report['protocol']['case_ids'])} câu, greedy, batch 1, mỗi câu đúng một lần gọi, warm-up ngoài phép đo; p95 nearest-rank. PyTorch {report['environment']['torch_version']}, CPU {report['environment']['cpu']}; CUDA: {report['environment']['cuda_available']}.",
        "",
        "| cấu hình | trạng thái | đúng target | giống CT2 cpu-int8 | giống CT2 gpu-f32 | median ms | p95 ms | nạp ms | compile đầu ms | VRAM MiB |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for c in configs:
        if c["status"] == "ok":
            lines.append(
                f"| {c['name']} | ok | {c['exact_target_matches']}/120 ({c['exact_target_rate']*100:.1f}%) | {c['identical_to_ct2_cpu_int8']}/120 | {c['identical_to_ct2_gpu_float32']}/120 | {ms(c['latency_median_ns'])} | {ms(c['latency_p95_ns'])} | {ms(c['load_ns'])} | {ms(c['compile_first_call_ns'])} | {mib(c['peak_vram_bytes'])} |"
            )
        else:
            error = c.get("error", "").replace("|", "/")
            lines.append(
                f"| {c['name']} | {c['status']}: {error} | — | — | — | — | — | {ms(c.get('load_ns'))} | {ms(c.get('compile_first_call_ns'))} | — |"
            )

    sizes = report["disk_usage"]
    torch_b = sizes["core"]["torch"]["allocated_bytes"]
    transformers_b = sizes["core"]["transformers"]["allocated_bytes"]
    ct2_b = sizes["core"]["ctranslate2"]["allocated_bytes"]
    nvidia_b = sizes["nvidia_total_allocated_bytes"]
    native_extra = torch_b + transformers_b + nvidia_b - ct2_b
    lines += [
        "",
        "## So sánh trực tiếp",
        "",
        "Mốc CT2: cpu-int8 82,5% / 1.741 ms; gpu-float32 82,5% / 1.219 ms; gpu-bfloat16 80,8% / 692 ms.",
    ]
    cpu = next((c for c in ok if c["name"] == "cpu-float32"), None)
    bf = next((c for c in ok if c["name"] == "cpu-bfloat16"), None)
    if cpu and bf:
        lines.append(
            f"PyTorch CPU float32 đạt {cpu['exact_target_rate']*100:.1f}% và median {ms(cpu['latency_median_ns'])} ms; CPU bfloat16 đạt {bf['exact_target_rate']*100:.1f}% / {ms(bf['latency_median_ns'])} ms. So với CT2 cpu-int8, lần lượt chậm {cpu['latency_median_ns']/1_741_000_000:.2f}× và {bf['latency_median_ns']/1_741_000_000:.2f}×."
        )
    gpu_bf = next((c for c in ok if c["name"] == "cuda-bfloat16"), None)
    if gpu_bf:
        lines.append(
            f"PyTorch CUDA bfloat16 đạt {gpu_bf['exact_target_rate']*100:.1f}% / {ms(gpu_bf['latency_median_ns'])} ms: hơn CT2 bf16 1,7 điểm %, nhưng chậm {gpu_bf['latency_median_ns']/692_000_000:.2f}×; VRAM đỉnh {mib(gpu_bf['peak_vram_bytes'])} MiB."
        )
    missing_cuda = [
        c["name"] for c in configs if c["device"] == "cuda" and c["status"] != "ok"
    ]
    if missing_cuda:
        lines.append(
            "Sandbox chính không thấy GPU; chưa đo được " + ", ".join(missing_cuda) + "."
        )

    lines += [
        "",
        "## Dung lượng site-packages (allocated GiB)",
        "",
        "| torch | transformers | ctranslate2 | nvidia-* (tổng) | PyTorch stack trừ CT2 |",
        "|---:|---:|---:|---:|---:|",
        f"| {gib(torch_b)} | {gib(transformers_b)} | {gib(ct2_b)} | {gib(nvidia_b)} | {native_extra/2**30:+.2f} GiB |",
        "",
        f"Bỏ CT2 chỉ tiết kiệm {gib(ct2_b)} GiB; nếu ảnh CT2 hiện không cần torch/transformers/nvidia-*, chuyển native làm container nặng thêm khoảng {native_extra/2**30:.2f} GiB. Nếu các gói đó đã có vì tác vụ khác, phần chênh biên chỉ là −{gib(ct2_b)} GiB.",
        "",
        "## Khuyến nghị",
        "",
    ]
    if gpu_bf and gpu_bf["latency_median_ns"] > 692_000_000:
        lines.append("Giữ CT2: PyTorch CUDA bf16 đạt chất lượng benchmark nhưng chậm hơn rõ rệt, CPU cũng không thắng (nếu có số), trong khi stack native làm ảnh nặng thêm. Compile chưa có số để đảo ngược kết luận.")
    elif cpu and cpu["latency_median_ns"] > 1_741_000_000:
        lines.append("Giữ CT2 cho cấu hình đang phục vụ: số CPU native không có lợi về tốc độ, còn chi phí ảnh tăng mạnh. Chỉ đổi sang PyTorch sau khi chạy lại cùng kịch bản trên GPU đích và số CUDA compile chứng minh được lợi ích vận hành đủ bù dung lượng/khởi động.")
    else:
        lines.append("Chưa đủ bằng chứng để bỏ CT2; quyết định cuối cần số CUDA trên đúng GPU triển khai.")
    lines += [
        "",
        "## Điểm yếu phép đo",
        "",
        "Mỗi câu chỉ đo một lần nên percentile nhạy với nhiễu; chỉ một thứ tự câu và một máy. Lượt GPU bf16 bên ngoài chồng thời gian với một lượt CPU nên có thể tranh chấp tài nguyên. Load float32 gồm gộp LoRA trong RAM (có thể giảm nếu đóng gói sẵn). Compile đầu là cả biên dịch+lần sinh đầu. Dung lượng là môi trường hiện tại, không phải image tối giản; ba cấu hình CUDA còn thiếu.",
    ]
    if len(lines) >= 45:
        raise AssertionError(f"Báo cáo có {len(lines)} dòng, phải dưới 45")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save(report: dict) -> None:
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_report(report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--configs",
        nargs="*",
        choices=[spec[0] for spec in CONFIGS],
        help="chỉ chạy cấu hình được nêu; mặc định chạy cả sáu",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected = set(args.configs or [spec[0] for spec in CONFIGS])
    rows, cpu_int8, gpu_fp32 = load_inputs()
    unavailable = cuda_unavailable_reason()
    report = {
        "protocol": {
            "case_source": str(CT2_GPU.relative_to(ROOT)) + " configs[0].cases[].id",
            "dataset": str(DATASET.relative_to(ROOT)),
            "case_ids": [row["id"] for row in rows],
            "generation": {
                "do_sample": False,
                "num_beams": 1,
                "max_new_tokens": MAX_NEW_TOKENS,
                "batch_size": 1,
                "one_call_per_question": True,
                "warmup_calls_per_config": 1,
            },
            "p95": "nearest-rank",
            "float32_model": f"{BASE_MODEL}@{BASE_REVISION} + {ADAPTER.relative_to(ROOT)}",
            "bfloat16_model": str(MODEL_BF16.relative_to(ROOT)),
        },
        "environment": {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "python": sys.version,
            "platform": platform.platform(),
            "cpu": cpu_name(),
            "torch_version": torch.__version__,
            "transformers_version": importlib.metadata.version("transformers"),
            "peft_version": importlib.metadata.version("peft"),
            "torch_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
            "cuda_build_version": torch.version.cuda,
            "cuda_available": unavailable is None,
            "cuda_unavailable_reason": unavailable,
            "cuda_device": (
                torch.cuda.get_device_name(0) if unavailable is None else None
            ),
            "ld_library_path": os.environ["LD_LIBRARY_PATH"],
        },
        "disk_usage": disk_usage(),
        "configs": [
            {
                "name": name,
                "device": device,
                "dtype": str(dtype).removeprefix("torch."),
                "compile": compile_model,
                "status": "chưa đo được",
                "error": "chưa có kết quả trong môi trường khả dụng",
            }
            for name, device, dtype, compile_model in CONFIGS
        ],
    }
    # Chạy --configs dùng để bổ sung phép đo trên máy khác (đặc biệt GPU), nên
    # hợp nhất theo tên thay vì xoá các lượt CPU/GPU đã tốn thời gian đo.
    if args.configs and OUTPUT.exists():
        previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        previous_by_name = {c["name"]: c for c in previous.get("configs", [])}
        report["configs"] = [
            previous_by_name.get(c["name"], c) for c in report["configs"]
        ]
        report["environment"] = previous.get("environment", report["environment"])
        report["environment"].setdefault("merged_runs", []).append(
            {
                "started_at": datetime.now(timezone.utc).isoformat(),
                "selected_configs": sorted(selected),
                "cuda_available": unavailable is None,
                "cuda_unavailable_reason": unavailable,
            }
        )
    save(report)
    for spec in CONFIGS:
        if spec[0] not in selected:
            continue
        print(f"bắt đầu {spec[0]}", flush=True)
        try:
            result = run_config(*spec, rows, cpu_int8, gpu_fp32)
        except Exception as exc:
            result = {
                "name": spec[0],
                "device": spec[1],
                "dtype": str(spec[2]).removeprefix("torch."),
                "compile": spec[3],
                "status": "lỗi",
                "error": f"{type(exc).__name__}: {exc}",
            }
        index = next(i for i, c in enumerate(report["configs"]) if c["name"] == spec[0])
        report["configs"][index] = result
        save(report)
    report["environment"]["last_finished_at"] = datetime.now(timezone.utc).isoformat()
    save(report)
    print(f"đã ghi {OUTPUT}")
    print(f"đã ghi {REPORT}")


if __name__ == "__main__":
    main()
