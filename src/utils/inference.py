"""Shared inference utilities for embedding extraction and logit computation.

Provides DRY functions used by both train.py and evaluate.py.
"""

from __future__ import annotations

import numpy as np
import onnxruntime as ort
import torch
from torch.utils.data import DataLoader


def extract_embeddings(
    model: torch.nn.Module,
    dataset,
    batch_size: int = 64,
) -> np.ndarray:
    """Extract CLS token embeddings from a model's base encoder."""
    model.eval()
    device = next(model.parameters()).device
    use_amp = device.type == "cuda"
    embeddings: list[np.ndarray] = []

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        pin_memory=(device.type == "cuda"),
        num_workers=0,
    )

    with torch.no_grad():
        for batch in loader:
            ids = batch["input_ids"].to(device, non_blocking=True)
            mask = batch["attention_mask"].to(device, non_blocking=True)

            base = model.roberta if hasattr(model, "roberta") else model

            with torch.amp.autocast("cuda", enabled=use_amp):
                out = base(input_ids=ids, attention_mask=mask)

            embeddings.append(out.last_hidden_state[:, 0, :].cpu().numpy())

    return np.vstack(embeddings)


def get_logits(
    model: torch.nn.Module,
    dataset,
    batch_size: int = 16,
) -> np.ndarray:
    """Run inference and return raw logits."""
    model.eval()
    device = next(model.parameters()).device
    use_amp = device.type == "cuda"
    all_logits: list[torch.Tensor] = []

    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        pin_memory=(device.type == "cuda"),
        num_workers=0,
    )

    with torch.no_grad():
        for batch in loader:
            ids = batch["input_ids"].to(device, non_blocking=True)
            mask = batch["attention_mask"].to(device, non_blocking=True)

            with torch.amp.autocast("cuda", enabled=use_amp):
                out = model(input_ids=ids, attention_mask=mask)

            all_logits.append(out.logits.cpu())

    return torch.cat(all_logits, dim=0).numpy()


def load_onnx_session(onnx_path: str, providers: list[str] = None) -> ort.InferenceSession:
    """Load an ONNX model into an InferenceSession."""
    if providers is None:
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    return ort.InferenceSession(onnx_path, providers=providers)


def predict_onnx(
    session: ort.InferenceSession,
    input_ids: np.ndarray,
    attention_mask: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Run inference using an ONNX session and return multi-label predictions."""
    ort_inputs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
    }
    ort_outs = session.run(None, ort_inputs)
    logits = ort_outs[0]
    probs = 1 / (1 + np.exp(-logits))
    return (probs >= threshold).astype(np.intp)
