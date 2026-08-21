#!/usr/bin/env python3
"""Xuất T5Gemma2 đã gộp sang ba đồ thị ONNX bằng tracer cũ của torch.onnx."""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer
from transformers.cache_utils import EncoderDecoderCache
from transformers.modeling_outputs import BaseModelOutput


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "artifacts/serving-models/merged-bf16"
OUTPUT_DIR = ROOT / "artifacts/benchmarks/onnx-export"
NUM_LAYERS = 18
OPSET = 18


def set_float32(config) -> None:
    config.dtype = torch.float32
    config.encoder.dtype = torch.float32
    config.encoder.text_config.dtype = torch.float32
    config.decoder.dtype = torch.float32
    # Eager attention tạo mask bằng toán tử tensor thường; đường SDPA dùng
    # torch.vmap mà legacy JIT tracer không biểu diễn được (unordered_map::at).
    config._attn_implementation = "eager"
    config.encoder._attn_implementation = "eager"
    config.encoder.text_config._attn_implementation = "eager"
    config.decoder._attn_implementation = "eager"


class Encoder(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.encoder = model.get_encoder()

    def forward(self, input_ids, attention_mask):
        # Dạng additive [batch, 1, 1, key]. Broadcast theo query; bộ đo batch 1
        # không padding và ngắn hơn sliding window nên full/sliding giống nhau.
        padding_bias = (1.0 - attention_mask.to(torch.float32))[:, None, None, :] * -1.0e9
        return self.encoder(
            input_ids=input_ids,
            attention_mask={"full_attention": padding_bias, "sliding_attention": padding_bias},
            return_dict=False,
        )[0]


def flatten_cache(cache) -> tuple[torch.Tensor, ...]:
    answer = []
    for layer in cache.self_attention_cache.layers:
        answer += [layer.keys, layer.values]
    for layer in cache.cross_attention_cache.layers:
        answer += [layer.keys, layer.values]
    return tuple(answer)


def make_cache(flat: tuple[torch.Tensor, ...]) -> EncoderDecoderCache:
    # DynamicLayer (tuple 4 phần tử) là tương đương cache trượt khi chuỗi sinh
    # ngắn hơn cửa sổ 512. Quan trọng hơn, độ dài past vẫn là shape động trong
    # đồ thị; DynamicSlidingWindowLayer giữ một Python int và tracer sẽ đóng cứng.
    self_kv = flat[: 2 * NUM_LAYERS]
    cross_kv = flat[2 * NUM_LAYERS :]
    combined = tuple(
        (
            self_kv[2 * i],
            self_kv[2 * i + 1],
            cross_kv[2 * i],
            cross_kv[2 * i + 1],
        )
        for i in range(NUM_LAYERS)
    )
    return EncoderDecoderCache(combined)


class DecoderInit(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, decoder_input_ids, encoder_attention_mask, encoder_hidden_state):
        batch, query = decoder_input_ids.shape
        self_bias = torch.zeros(
            (batch, 1, query, query), dtype=encoder_hidden_state.dtype,
            device=decoder_input_ids.device,
        )
        cross_bias = (1.0 - encoder_attention_mask.to(encoder_hidden_state.dtype))[:, None, None, :] * -1.0e9
        output = self.model(
            decoder_input_ids=decoder_input_ids,
            decoder_attention_mask={"full_attention": self_bias, "sliding_attention": self_bias},
            attention_mask={"full_attention": cross_bias},
            encoder_outputs=BaseModelOutput(last_hidden_state=encoder_hidden_state),
            use_cache=True,
            return_dict=True,
        )
        return (output.logits[:, -1, :], *flatten_cache(output.past_key_values))


class DecoderCached(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, decoder_input_ids, encoder_attention_mask, encoder_hidden_state, *flat):
        batch, query = decoder_input_ids.shape
        past_length = flat[0].shape[2]
        self_bias = torch.zeros(
            (batch, 1, query, past_length + query),
            dtype=encoder_hidden_state.dtype, device=decoder_input_ids.device,
        )
        cross_bias = (1.0 - encoder_attention_mask.to(encoder_hidden_state.dtype))[:, None, None, :] * -1.0e9
        output = self.model(
            decoder_input_ids=decoder_input_ids,
            decoder_attention_mask={"full_attention": self_bias, "sliding_attention": self_bias},
            attention_mask={"full_attention": cross_bias},
            encoder_outputs=BaseModelOutput(last_hidden_state=encoder_hidden_state),
            past_key_values=make_cache(flat),
            use_cache=True,
            return_dict=True,
        )
        self_cache = output.past_key_values.self_attention_cache.layers
        present = tuple(t for layer in self_cache for t in (layer.keys, layer.values))
        return (output.logits[:, -1, :], *present)


def kv_names(prefix: str, kind: str) -> list[str]:
    return [f"{prefix}_{kind}_{i}_{kv}" for i in range(NUM_LAYERS) for kv in ("key", "value")]


def export_graph(module, args, path: Path, input_names, output_names, dynamic_axes) -> int:
    started = time.perf_counter_ns()
    torch.onnx.export(
        module,
        args,
        path,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes,
        opset_version=OPSET,
        dynamo=False,
        external_data=True,
        do_constant_folding=True,
    )
    return time.perf_counter_ns() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [OUTPUT_DIR / name for name in ("encoder.onnx", "decoder-init.onnx", "decoder-cache.onnx")]
    if not args.force and all(path.exists() for path in paths):
        print("Ba đồ thị đã tồn tại; dùng --force để xuất lại.")
        return

    config = AutoConfig.from_pretrained(MODEL_DIR, local_files_only=True)
    set_float32(config)
    load_started = time.perf_counter_ns()
    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_DIR, config=config, dtype=torch.float32, local_files_only=True
    ).eval()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
    load_ns = time.perf_counter_ns() - load_started
    encoded = tokenizer("Liệt kê thông tin cố vấn học tập", return_tensors="pt")
    input_ids, attention_mask = encoded["input_ids"], encoded["attention_mask"]
    decoder_ids = torch.tensor([[0]], dtype=torch.long)

    # Dùng no_grad thay vì inference_mode: JIT tracer cần lưu tensor mẫu để
    # dựng graph và từ chối tensor mang cờ inference ở bước xuất kế tiếp.
    with torch.no_grad():
        hidden = Encoder(model)(input_ids, attention_mask)
        init_values = DecoderInit(model)(decoder_ids, attention_mask, hidden)
        first_token = init_values[0].argmax(-1, keepdim=True)
        flat_cache = init_values[1:]
        cached_values = DecoderCached(model)(
            first_token, attention_mask, hidden, *flat_cache
        )
        eager_tokens = [int(first_token.item()), int(cached_values[0].argmax(-1).item())]

    timings = {}
    print("Xuất encoder...", flush=True)
    timings["encoder_ns"] = export_graph(
        Encoder(model),
        (input_ids, attention_mask),
        paths[0],
        ["input_ids", "attention_mask"],
        ["encoder_hidden_state"],
        {
            "input_ids": {0: "batch", 1: "encoder_sequence"},
            "attention_mask": {0: "batch", 1: "encoder_sequence"},
            "encoder_hidden_state": {0: "batch", 1: "encoder_sequence"},
        },
    )

    self_present = kv_names("present", "self")
    cross_present = kv_names("present", "cross")
    init_dynamic = {
        "decoder_input_ids": {0: "batch", 1: "decoder_sequence"},
        "encoder_attention_mask": {0: "batch", 1: "encoder_sequence"},
        "encoder_hidden_state": {0: "batch", 1: "encoder_sequence"},
        "logits": {0: "batch"},
    }
    for name in self_present:
        init_dynamic[name] = {0: "batch", 2: "self_sequence"}
    for name in cross_present:
        init_dynamic[name] = {0: "batch", 2: "encoder_sequence"}
    print("Xuất decoder bước đầu...", flush=True)
    timings["decoder_init_ns"] = export_graph(
        DecoderInit(model),
        (decoder_ids, attention_mask, hidden),
        paths[1],
        ["decoder_input_ids", "encoder_attention_mask", "encoder_hidden_state"],
        ["logits", *self_present, *cross_present],
        init_dynamic,
    )

    past_self = kv_names("past", "self")
    past_cross = kv_names("past", "cross")
    cache_dynamic = {
        "decoder_input_ids": {0: "batch", 1: "decoder_sequence"},
        "encoder_attention_mask": {0: "batch", 1: "encoder_sequence"},
        "encoder_hidden_state": {0: "batch", 1: "encoder_sequence"},
        "logits": {0: "batch"},
    }
    for name in past_self:
        cache_dynamic[name] = {0: "batch", 2: "past_self_sequence"}
    for name in past_cross:
        cache_dynamic[name] = {0: "batch", 2: "encoder_sequence"}
    for name in self_present:
        cache_dynamic[name] = {0: "batch", 2: "present_self_sequence"}
    print("Xuất decoder có KV cache...", flush=True)
    timings["decoder_cache_ns"] = export_graph(
        DecoderCached(model),
        (first_token, attention_mask, hidden, *flat_cache),
        paths[2],
        ["decoder_input_ids", "encoder_attention_mask", "encoder_hidden_state", *past_self, *past_cross],
        ["logits", *self_present],
        cache_dynamic,
    )
    manifest = {
        "format": "float32",
        "opset": OPSET,
        "exporter": "torch.onnx.export legacy tracer (dynamo=False)",
        "model": str(MODEL_DIR.relative_to(ROOT)),
        "num_layers": NUM_LAYERS,
        "load_ns": load_ns,
        "export_timings_ns": timings,
        "eager_first_two_tokens": eager_tokens,
        "files": [path.name for path in paths],
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    del model
    gc.collect()
    print("Đã xuất:", ", ".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
