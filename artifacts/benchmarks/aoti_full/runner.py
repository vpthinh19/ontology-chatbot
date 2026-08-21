#!/usr/bin/env python3
"""Thin Python wrapper around the full T5Gemma2 AOTInductor runtime."""

from __future__ import annotations

import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
_site_packages = next((ROOT / ".venv/lib").glob("python*/site-packages"))
_cuda_libs = [
    _site_packages / "nvidia/cublas/lib",
    _site_packages / "nvidia/cudnn/lib",
]
_existing_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
os.environ["LD_LIBRARY_PATH"] = ":".join(
    [str(path) for path in _cuda_libs]
    + ([_existing_ld_path] if _existing_ld_path else [])
)

import torch
from transformers import AutoTokenizer

MODEL_DIR = ROOT / "artifacts/serving-models/merged-bf16"
DEFAULT_PACKAGE_DIR = Path(__file__).resolve().parent / "package"

MAX_SOURCE_LENGTH = 128
MAX_NEW_TOKENS = 320
NUM_LAYERS = 18
NUM_KV_HEADS = 1
HEAD_DIM = 256
MIN_PADDED_SOURCE = 15


class AOTIGenerator:
    """Greedy batch-1 generation with all model computation in AOTI packages."""

    def __init__(self, package_dir: str | Path = DEFAULT_PACKAGE_DIR, device: str = "cuda"):
        if device != "cuda":
            raise ValueError("the packages are compiled for CUDA; device must be 'cuda'")
        if not torch.cuda.is_available():
            raise RuntimeError("torch.cuda.is_available() trả về False")
        package_dir = Path(package_dir)
        encoder_path = package_dir / "encoder.pt2"
        decoder_path = package_dir / "decoder.pt2"
        if not encoder_path.is_file() or not decoder_path.is_file():
            raise FileNotFoundError(
                f"missing AOTI package; run build.py first ({encoder_path}, {decoder_path})"
            )
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, local_files_only=True)
        self.encoder = torch._inductor.aoti_load_package(encoder_path)
        self.decoder = torch._inductor.aoti_load_package(decoder_path)
        self.pad_token_id = self.tokenizer.pad_token_id or 0
        self.eos_token_id = self.tokenizer.eos_token_id
        self.start_token_id = self.tokenizer.bos_token_id
        if self.start_token_id is None:
            self.start_token_id = 2
        # Ô vị trí cấp riêng một lần rồi ghi tại chỗ. Cắt lát từ một dãy dài cho ra
        # con trỏ lệch tám byte ở các bước lẻ, và đồ thị đã biên dịch giả định căn
        # mười sáu byte nên phải sao chép lại trước mỗi bước.
        self.position = torch.zeros(1, dtype=torch.long, device="cuda")

    @torch.inference_mode()
    def generate(self, text: str) -> str:
        """Return one SPARQL string without calling Transformers generation."""
        encoded = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_SOURCE_LENGTH,
        )
        input_ids = encoded["input_ids"].cuda()
        attention_mask = encoded["attention_mask"].cuda()
        padded = max(15, 8 * math.ceil((input_ids.shape[1] + 1) / 8) - 1)
        input_ids = torch.nn.functional.pad(
            input_ids, (0, padded - input_ids.shape[1]), value=self.pad_token_id
        )
        attention_mask = torch.nn.functional.pad(
            attention_mask, (0, padded - attention_mask.shape[1]), value=0
        )

        encoder_output = self.encoder(input_ids, attention_mask)
        encoder_hidden, cross_keys, cross_values = encoder_output
        self_keys = torch.zeros(
            (NUM_LAYERS, 1, NUM_KV_HEADS, MAX_NEW_TOKENS, HEAD_DIM),
            dtype=torch.bfloat16,
            device="cuda",
        )
        self_values = torch.zeros_like(self_keys)
        token = torch.tensor([[self.start_token_id]], dtype=torch.long, device="cuda")
        generated: list[int] = []
        for step in range(MAX_NEW_TOKENS):
            self.position.fill_(step)
            token = self.decoder(
                token,
                self.position,
                encoder_hidden,
                attention_mask,
                self_keys,
                self_values,
                cross_keys,
                cross_values,
            )[0]
            token_id = int(token.item())
            generated.append(token_id)
            if token_id == self.eos_token_id:
                break
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()


_default_generator: AOTIGenerator | None = None


def generate(text: str) -> str:
    """Convenience API requested by the benchmark task."""
    global _default_generator
    if _default_generator is None:
        _default_generator = AOTIGenerator()
    return _default_generator.generate(text)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    arguments = parser.parse_args()
    print(AOTIGenerator(arguments.package_dir).generate(arguments.text))
