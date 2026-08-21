#!/usr/bin/env python3
"""Build and verify the complete T5Gemma2 greedy-generation AOTI runtime.

The runtime consists of two AOTInductor packages:

* ``encoder.pt2`` runs the encoder and materializes all decoder cross-attention
  K/V tensors once per request.
* ``decoder.pt2`` runs one decoder token and mutates a fixed-size self-attention
  cache in place.  Its shapes therefore do not grow during generation.

Run from the repository root with ``.venv/bin/python``.  By default this builds
the packages and performs the required 40-row comparison.  ``--build-only`` is
useful when build and benchmark have to be run in separate GPU jobs.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import random
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any

# These must be set before importing torch.  Keep caches in writable locations;
# the developer environment may have a read-only ccache under $HOME.
os.environ.setdefault("CUDA_HOME", "/usr/local/cuda")
os.environ["PATH"] = f"{os.environ['CUDA_HOME']}/bin:{os.environ.get('PATH', '')}"
os.environ["CCACHE_DISABLE"] = "1"
os.environ.setdefault("TORCHINDUCTOR_CACHE_DIR", "/tmp/ontology-chatbot-aoti-full")

ROOT = Path(__file__).resolve().parents[3]
# The CUDA wheels keep these outside the ordinary torch RPATH.  Mirror the
# deployment environment described by the benchmark task when it is not
# already supplied by the caller.
_site_packages = next((ROOT / ".venv/lib").glob("python*/site-packages"))
_cuda_wheel_libs = [
    _site_packages / "nvidia/cublas/lib",
    _site_packages / "nvidia/cudnn/lib",
]
_existing_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["LD_LIBRARY_PATH"] = ":".join(
    [str(path) for path in _cuda_wheel_libs]
    + ([_existing_ld_path] if _existing_ld_path else [])
)
HERE = Path(__file__).resolve().parent
MODEL_DIR = ROOT / "artifacts/serving-models/merged-bf16"
DATASET = ROOT / "resources/dataset/test.jsonl"
PACKAGE_DIR = HERE / "package"
ENCODER_PACKAGE = PACKAGE_DIR / "encoder.pt2"
DECODER_PACKAGE = PACKAGE_DIR / "decoder.pt2"
BUILD_META = PACKAGE_DIR / "build.json"
REPORT = HERE / "report.md"

MAX_SOURCE_LENGTH = 128
MAX_NEW_TOKENS = 320
NUM_LAYERS = 18
NUM_KV_HEADS = 1
HEAD_DIM = 256
HIDDEN_SIZE = 640
PAD_MULTIPLE = 8
MIN_PADDED_SOURCE = 15  # k >= 2; this is also the export constraint minimum.


def _import_runtime():
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    return torch, AutoModelForSeq2SeqLM, AutoTokenizer


def padded_source_length(length: int) -> int:
    """Return the smallest valid derived length ``8*k - 1``."""
    if length > MAX_SOURCE_LENGTH:
        raise ValueError(f"source has {length} tokens; maximum is {MAX_SOURCE_LENGTH}")
    return max(MIN_PADDED_SOURCE, PAD_MULTIPLE * math.ceil((length + 1) / PAD_MULTIPLE) - 1)


class _TensorSelfCache:
    """Minimal static Cache protocol used by T5Gemma2's masking/attention code."""

    def __init__(self, keys, values, position, layer_types: tuple[str, ...]):
        self.keys = keys
        self.values = values
        self.position = position
        self.is_sliding = [kind == "sliding_attention" for kind in layer_types]

    def update(self, key_states, value_states, layer_idx: int, *args, **kwargs):
        # All 18 layers have identical K/V geometry in this checkpoint.  The
        # input mutation is intentional: AOTI preserves it, so only the token is
        # returned across the Python/C++ boundary.
        keys = self.keys[layer_idx]
        values = self.values[layer_idx]
        keys.index_copy_(2, self.position, key_states)
        values.index_copy_(2, self.position, value_states)
        return keys, values

    def get_query_offset(self, layer_idx: int = 0):
        return self.position[0]

    def get_mask_sizes(self, query_length: int, layer_idx: int):
        return MAX_NEW_TOKENS, 0

    def get_seq_length(self, layer_idx: int = 0):
        return self.position[0]


class _CrossLayer:
    def __init__(self, keys, values):
        self.keys = keys
        self.values = values


class _TensorCrossCache:
    def __init__(self, keys, values):
        self.layers = [_CrossLayer(keys[i], values[i]) for i in range(NUM_LAYERS)]


class _TensorEncoderDecoderCache:
    """The exact attributes consumed by T5Gemma2MergedAttention."""

    def __init__(self, self_cache, cross_cache):
        self.self_attention_cache = self_cache
        self.cross_attention_cache = cross_cache
        self.is_updated = {i: True for i in range(NUM_LAYERS)}


def make_modules(model, torch):
    """Create export wrappers without retaining the outer Transformers model."""

    class EncoderAndCrossCache(torch.nn.Module):
        def __init__(self, source_model):
            super().__init__()
            self.encoder = source_model.get_encoder()
            # Register only the K/V projections and K normalizers needed to
            # materialize cross-attention state.  They share the trained tensors.
            self.cross_attentions = torch.nn.ModuleList(
                layer.self_attn for layer in source_model.model.decoder.layers
            )

        def forward(self, input_ids, attention_mask):
            hidden = self.encoder(
                input_ids=input_ids, attention_mask=attention_mask, return_dict=False
            )[0]
            shape = (hidden.shape[0], hidden.shape[1], -1, HEAD_DIM)
            keys = []
            values = []
            for attention in self.cross_attentions:
                key = attention.k_proj(hidden).view(shape).transpose(1, 2)
                key = attention.k_norm(key)
                value = attention.v_proj(hidden).view(shape).transpose(1, 2)
                keys.append(key)
                values.append(value)
            return hidden, torch.stack(keys), torch.stack(values)

    class DecoderStep(torch.nn.Module):
        def __init__(self, source_model):
            super().__init__()
            self.decoder = source_model.get_decoder()
            self.lm_head = source_model.lm_head
            self.layer_types = tuple(source_model.config.decoder.layer_types)

        def forward(
            self,
            token,
            position,
            encoder_hidden,
            encoder_attention_mask,
            self_keys,
            self_values,
            cross_keys,
            cross_values,
        ):
            self_cache = _TensorSelfCache(
                self_keys, self_values, position, self.layer_types
            )
            cache = _TensorEncoderDecoderCache(
                self_cache, _TensorCrossCache(cross_keys, cross_values)
            )
            hidden = self.decoder(
                input_ids=token,
                attention_mask=None,
                position_ids=position.view(1, 1),
                past_key_values=cache,
                use_cache=True,
                encoder_hidden_states=encoder_hidden,
                encoder_attention_mask=encoder_attention_mask,
                return_dict=False,
            )[0]
            logits = self.lm_head(hidden[:, -1:, :])
            return torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)

    return EncoderAndCrossCache(model).eval(), DecoderStep(model).eval()


def _cuda_error(torch) -> str | None:
    if torch.cuda.is_available():
        return None
    details = ["torch.cuda.is_available() trả về False"]
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"], text=True, capture_output=True, timeout=10
        )
        output = (result.stdout + result.stderr).strip()
        details.append(f"nvidia-smi -L (exit {result.returncode}): {output}")
    except Exception as exc:  # pragma: no cover - depends on host setup
        details.append(f"nvidia-smi -L: {type(exc).__name__}: {exc}")
    return "\n".join(details)


def cpu_smoke() -> dict[str, Any]:
    """Verify cache semantics and exportability without claiming a GPU result."""
    torch, AutoModelForSeq2SeqLM, AutoTokenizer = _import_runtime()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, local_files_only=True
    ).eval()
    encoder, decoder = make_modules(model, torch)
    encoded = tokenizer(
        "Cho hỏi mình cần tra cứu văn bản tại Điều 2 Quy chế 1052?",
        return_tensors="pt",
        truncation=True,
        max_length=MAX_SOURCE_LENGTH,
    )
    length = padded_source_length(encoded["input_ids"].shape[1])
    pad = tokenizer.pad_token_id or 0
    ids = torch.nn.functional.pad(
        encoded["input_ids"], (0, length - encoded["input_ids"].shape[1]), value=pad
    )
    mask = torch.nn.functional.pad(
        encoded["attention_mask"],
        (0, length - encoded["attention_mask"].shape[1]),
        value=0,
    )
    start = model.config.bos_token_id
    with torch.inference_mode():
        reference = model.generate(
            input_ids=ids,
            attention_mask=mask,
            do_sample=False,
            num_beams=1,
            max_new_tokens=8,
        )[0].tolist()
        hidden, cross_keys, cross_values = encoder(ids, mask)
        self_keys = torch.zeros(
            (NUM_LAYERS, 1, NUM_KV_HEADS, MAX_NEW_TOKENS, HEAD_DIM),
            dtype=torch.bfloat16,
        )
        self_values = torch.zeros_like(self_keys)
        token = torch.tensor([[start]], dtype=torch.long)
        generated = [start]
        for step in range(8):
            token = decoder(
                token,
                torch.tensor([step]),
                hidden,
                mask,
                self_keys,
                self_values,
                cross_keys,
                cross_values,
            )
            generated.append(int(token.item()))

    k = torch.export.Dim("source_blocks", min=2, max=17)
    source = 8 * k - 1
    torch.export.export(
        encoder,
        (ids, mask),
        dynamic_shapes={"input_ids": {1: source}, "attention_mask": {1: source}},
        strict=False,
    )
    # Create ordinary tensors outside inference mode: decoder export contains
    # intentional in-place mutation and inference tensors disallow that here.
    self_keys = torch.zeros(
        (NUM_LAYERS, 1, NUM_KV_HEADS, MAX_NEW_TOKENS, HEAD_DIM), dtype=torch.bfloat16
    )
    self_values = torch.zeros_like(self_keys)
    decoder_ep = torch.export.export(
        decoder,
        (
            torch.tensor([[start]], dtype=torch.long),
            torch.tensor([0]),
            hidden.clone(),
            mask,
            self_keys,
            self_values,
            cross_keys.clone(),
            cross_values.clone(),
        ),
        dynamic_shapes={
            "token": None,
            "position": None,
            "encoder_hidden": {1: source},
            "encoder_attention_mask": {1: source},
            "self_keys": None,
            "self_values": None,
            "cross_keys": {3: source},
            "cross_values": {3: source},
        },
        strict=False,
    )
    return {
        "reference_tokens": reference,
        "static_wrapper_tokens": generated,
        "same_first_8": reference == generated,
        "encoder_export": "ok",
        "decoder_export": "ok",
        "decoder_graph_nodes": len(list(decoder_ep.graph.nodes)),
    }


def _example_inputs(model, tokenizer, torch):
    encoded = tokenizer(
        "thủ tục đăng ký học phần gồm những bước nào và cần giấy tờ gì",
        return_tensors="pt",
        truncation=True,
        max_length=MAX_SOURCE_LENGTH,
    )
    length = padded_source_length(encoded["input_ids"].shape[1])
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
    ids = torch.nn.functional.pad(
        encoded["input_ids"], (0, length - encoded["input_ids"].shape[1]), value=pad
    ).cuda()
    mask = torch.nn.functional.pad(
        encoded["attention_mask"],
        (0, length - encoded["attention_mask"].shape[1]),
        value=0,
    ).cuda()
    # T5Gemma2 không khai token mở đầu bộ giải mã ở cấu hình model lẫn cấu hình
    # sinh; khi cả hai đều thiếu thì token mở đầu là BOS.
    start = getattr(model.generation_config, "decoder_start_token_id", None)
    if start is None:
        start = getattr(model.config, "decoder_start_token_id", None)
    if start is None:
        start = model.generation_config.bos_token_id
    token = torch.tensor([[start]], dtype=torch.long, device="cuda")
    position = torch.tensor([0], dtype=torch.long, device="cuda")
    return ids, mask, token, position


def build_packages() -> dict[str, Any]:
    torch, AutoModelForSeq2SeqLM, AutoTokenizer = _import_runtime()
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    started_ns = time.perf_counter_ns()
    meta: dict[str, Any] = {
        "status": "building",
        "torch": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "model": str(MODEL_DIR.relative_to(ROOT)),
    }
    error = _cuda_error(torch)
    if error:
        try:
            meta["cpu_smoke"] = cpu_smoke()
        except Exception:
            meta["cpu_smoke"] = {"status": "failed", "error": traceback.format_exc()}
        meta.update(
            status="blocked-before-load",
            error=error,
            build_ns=time.perf_counter_ns() - started_ns,
        )
        BUILD_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        raise RuntimeError(error)

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, local_files_only=True
    ).cuda().eval()
    encoder_module, decoder_module = make_modules(model, torch)
    ids, mask, token, position = _example_inputs(model, tokenizer, torch)

    # The padded length is not an arbitrary dimension: the encoder requires the
    # derived 8*k-1 relation.  k=2..17 covers original inputs up through 128.
    k = torch.export.Dim("source_blocks", min=2, max=17)
    source = 8 * k - 1
    export_started = time.perf_counter_ns()
    encoder_ep = torch.export.export(
        encoder_module,
        (ids, mask),
        dynamic_shapes={
            "input_ids": {1: source},
            "attention_mask": {1: source},
        },
        strict=False,
    )
    with torch.inference_mode():
        hidden, cross_keys, cross_values = encoder_module(ids, mask)
    self_keys = torch.zeros(
        (NUM_LAYERS, 1, NUM_KV_HEADS, MAX_NEW_TOKENS, HEAD_DIM),
        dtype=torch.bfloat16,
        device="cuda",
    )
    self_values = torch.zeros_like(self_keys)
    decoder_args = (
        token,
        position,
        hidden,
        mask,
        self_keys,
        self_values,
        cross_keys,
        cross_values,
    )
    decoder_ep = torch.export.export(
        decoder_module,
        decoder_args,
        dynamic_shapes={
            "token": None,
            "position": None,
            "encoder_hidden": {1: source},
            "encoder_attention_mask": {1: source},
            "self_keys": None,
            "self_values": None,
            "cross_keys": {3: source},
            "cross_values": {3: source},
        },
        strict=False,
    )
    meta["export_ns"] = time.perf_counter_ns() - export_started

    compile_started = time.perf_counter_ns()
    configs = {"triton.cudagraphs": False}
    # ``package_path`` phải là chuỗi: hàm đóng gói so sánh giá trị trả về với tham
    # số truyền vào, mà nó luôn trả về chuỗi.
    torch._inductor.aoti_compile_and_package(
        encoder_ep, package_path=str(ENCODER_PACKAGE), inductor_configs=configs
    )
    torch._inductor.aoti_compile_and_package(
        decoder_ep, package_path=str(DECODER_PACKAGE), inductor_configs=configs
    )
    torch.cuda.synchronize()
    meta.update(
        status="ok",
        compile_ns=time.perf_counter_ns() - compile_started,
        build_ns=time.perf_counter_ns() - started_ns,
        peak_vram_bytes=torch.cuda.max_memory_allocated(),
        encoder_package_bytes=ENCODER_PACKAGE.stat().st_size,
        decoder_package_bytes=DECODER_PACKAGE.stat().st_size,
        package_bytes=ENCODER_PACKAGE.stat().st_size + DECODER_PACKAGE.stat().st_size,
    )
    BUILD_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    del decoder_ep, encoder_ep, decoder_module, encoder_module, model
    gc.collect()
    torch.cuda.empty_cache()
    return meta


def selected_rows() -> list[dict[str, Any]]:
    with DATASET.open(encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    rows = [row for row in rows if row["target"].startswith("SELECT")]
    random.Random(42).shuffle(rows)
    return rows[:40]


def _timed_regular(model, tokenizer, text: str, torch) -> tuple[str, int]:
    encoded = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_SOURCE_LENGTH,
    )
    encoded = {name: value.cuda() for name, value in encoded.items()}
    torch.cuda.synchronize()
    started = time.perf_counter_ns()
    with torch.inference_mode():
        output = model.generate(
            **encoded,
            do_sample=False,
            num_beams=1,
            max_new_tokens=MAX_NEW_TOKENS,
        )
    torch.cuda.synchronize()
    return tokenizer.decode(output[0], skip_special_tokens=True).strip(), time.perf_counter_ns() - started


def _extract_ldd(package_paths: tuple[Path, ...]) -> dict[str, str]:
    result: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="aoti-full-ldd-") as temporary:
        temp = Path(temporary)
        for package in package_paths:
            with zipfile.ZipFile(package) as archive:
                members = [name for name in archive.namelist() if name.endswith(".so")]
                for index, member in enumerate(members):
                    target = temp / f"{package.stem}-{index}.so"
                    target.write_bytes(archive.read(member))
                    proc = subprocess.run(
                        ["ldd", str(target)], text=True, capture_output=True
                    )
                    result[f"{package.name}:{member}"] = (proc.stdout + proc.stderr).strip()
    return result


def benchmark(meta: dict[str, Any]) -> dict[str, Any]:
    torch, AutoModelForSeq2SeqLM, AutoTokenizer = _import_runtime()
    from runner import AOTIGenerator

    error = _cuda_error(torch)
    if error:
        raise RuntimeError(error)
    rows = selected_rows()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)

    # Establish the requested ordinary model.generate oracle first, then release
    # its weights before loading AOTI so peak VRAM is meaningful for each path.
    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_DIR, dtype=torch.bfloat16, local_files_only=True
    ).cuda().eval()
    _timed_regular(model, tokenizer, rows[0]["input"], torch)
    regular_cases = []
    torch.cuda.reset_peak_memory_stats()
    for index, row in enumerate(rows, 1):
        prediction, latency = _timed_regular(model, tokenizer, row["input"], torch)
        regular_cases.append({"prediction": prediction, "latency_ns": latency})
        print(f"model.generate: {index}/40", flush=True)
    regular_peak = torch.cuda.max_memory_allocated()
    del model
    gc.collect()
    torch.cuda.empty_cache()

    generator = AOTIGenerator(PACKAGE_DIR)
    generator.generate(rows[0]["input"])
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats()
    aoti_cases = []
    for index, row in enumerate(rows, 1):
        torch.cuda.synchronize()
        started = time.perf_counter_ns()
        prediction = generator.generate(row["input"])
        torch.cuda.synchronize()
        aoti_cases.append(
            {"prediction": prediction, "latency_ns": time.perf_counter_ns() - started}
        )
        print(f"AOTI: {index}/40", flush=True)
    aoti_peak = torch.cuda.max_memory_allocated()

    same = sum(a["prediction"] == b["prediction"] for a, b in zip(regular_cases, aoti_cases))
    regular_exact = sum(
        case["prediction"] == row["target"].strip()
        for case, row in zip(regular_cases, rows)
    )
    aoti_exact = sum(
        case["prediction"] == row["target"].strip()
        for case, row in zip(aoti_cases, rows)
    )
    result = {
        "same_as_model_generate": same,
        "regular_exact": regular_exact,
        "aoti_exact": aoti_exact,
        "regular_median_ns": int(statistics.median(c["latency_ns"] for c in regular_cases)),
        "aoti_median_ns": int(statistics.median(c["latency_ns"] for c in aoti_cases)),
        "regular_peak_vram_bytes": regular_peak,
        "aoti_peak_vram_bytes": aoti_peak,
        "ldd": _extract_ldd((ENCODER_PACKAGE, DECODER_PACKAGE)),
        "cases": [
            {
                "id": row["id"],
                "target": row["target"],
                "regular": regular["prediction"],
                "aoti": aoti["prediction"],
                "regular_latency_ns": regular["latency_ns"],
                "aoti_latency_ns": aoti["latency_ns"],
            }
            for row, regular, aoti in zip(rows, regular_cases, aoti_cases)
        ],
    }
    (PACKAGE_DIR / "benchmark.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_report(meta, result)
    return result


def _seconds(value: int | None) -> str:
    return "—" if value is None else f"{value / 1e9:,.1f} s"


def _mib(value: int | None) -> str:
    return "—" if value is None else f"{value / 2**20:,.0f} MiB"


def write_report(meta: dict[str, Any], result: dict[str, Any] | None, failure: str | None = None) -> None:
    if result is None:
        comparison = "| model.generate thường | chưa đo | chưa đo | 2.569 ms (mốc) |\n| AOTI toàn vòng | chưa đo | chưa đo | chưa đo |\n| CT2 GPU float32 | — | — | 1.222 ms (mốc) |"
        verification = "**Chưa có phép kiểm 40 câu; không được coi là hoàn thành.**"
        runtime_peak = "—"
        ldd = "Chưa có `.so` để chạy `ldd`."
    else:
        regular_ms = result["regular_median_ns"] / 1e6
        aoti_ms = result["aoti_median_ns"] / 1e6
        comparison = (
            f"| model.generate thường | {result['regular_exact']}/40 | 40/40 | {regular_ms:,.1f} ms |\n"
            f"| AOTI toàn vòng | {result['aoti_exact']}/40 | {result['same_as_model_generate']}/40 | {aoti_ms:,.1f} ms |\n"
            "| CT2 GPU float32 | — | — | 1.222 ms (mốc) |"
        )
        verification = (
            f"**Truy vấn AOTI giống `model.generate` thường: {result['same_as_model_generate']}/40.**"
        )
        runtime_peak = _mib(result["aoti_peak_vram_bytes"])
        ldd = "\n\n".join(
            f"`{name}`\n\n```text\n{text}\n```" for name, text in result["ldd"].items()
        )
    package_size = meta.get("package_bytes")
    build_duration = _seconds(meta.get("build_ns")) if package_size is not None else "—"
    failure_text = failure or meta.get("error")
    status = meta.get("status", "unknown")
    report = f"""# AOTInductor: toàn bộ vòng sinh T5Gemma2

Trạng thái: **{status}**.

{verification}

| cấu hình | đúng target | giống model.generate | median/câu |
|---|---:|---:|---:|
{comparison}

| dựng gói | cỡ hai gói | VRAM đỉnh khi dựng | VRAM đỉnh AOTI |
|---:|---:|---:|---:|
| {build_duration} | {_mib(package_size)} | {_mib(meta.get('peak_vram_bytes'))} | {runtime_peak} |

Mốc so sánh do đề bài cung cấp: model thường 2.569 ms/câu; CT2 GPU float32 1.222 ms/câu.

## Cấu trúc đường chạy

`encoder.pt2` chạy encoder và tính cross-K/V của cả 18 lớp đúng một lần. `decoder.pt2` chạy một token, dùng self-K/V cấp sẵn đến 320 vị trí và cập nhật tensor tại chỗ. Vòng dừng EOS nằm trong lớp Python mỏng; đường chạy không nạp model Transformers và không gọi `model.generate`.

## ldd của `.so`

{ldd}
"""
    if failure_text:
        report += f"""

## Chặn và bằng chứng

Chặn tại bước: `{status}`.

Thời gian đến khi trả lỗi (gồm smoke test CPU): {_seconds(meta.get('build_ns'))}.

Thông báo lỗi nguyên văn:

```text
{failure_text}
```

Đã thử: kiểm tra `torch.cuda.is_available()`, `nvidia-smi -L`, đặt `CUDA_HOME=/usr/local/cuda`, đưa `nvcc` vào `PATH`, và tắt ccache chỉ-đọc bằng `CCACHE_DISABLE=1`. Phần xuất/biên dịch CUDA và phép kiểm 40 câu không thể chạy khi tiến trình không được cấp thiết bị NVIDIA.
"""
    if meta.get("cpu_smoke"):
        report += f"""

## Smoke test CPU (không thay thế benchmark GPU)

```json
{json.dumps(meta['cpu_smoke'], ensure_ascii=False, indent=2)}
```
"""
    REPORT.write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--benchmark-only", action="store_true")
    args = parser.parse_args()
    meta: dict[str, Any]
    try:
        if args.benchmark_only:
            meta = json.loads(BUILD_META.read_text(encoding="utf-8"))
        else:
            meta = build_packages()
        if not args.build_only:
            benchmark(meta)
        elif args.build_only:
            write_report(meta, None)
        return 0
    except Exception:
        failure = traceback.format_exc()
        if BUILD_META.exists():
            meta = json.loads(BUILD_META.read_text(encoding="utf-8"))
        else:
            meta = {"status": "failed"}
        recorded_error = meta.get("error", "")
        if not recorded_error or recorded_error not in failure:
            meta.update(
                status="benchmark-failed" if args.benchmark_only else "build-failed",
                error=failure,
            )
            PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_META.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        write_report(meta, None, failure)
        print(failure, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
