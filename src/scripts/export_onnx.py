"""Export fine-tuned PhoBERT models to ONNX format.

Exports models (BCE, ASL, ZLPR) with dynamic axes
for batch_size and sequence_length. Validates output consistency.

Usage:
    python -m src.scripts.export_onnx
"""

from __future__ import annotations

import os

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ..core.config import (
    MAX_LENGTH,
    MODEL_ASL_DIR,
    MODEL_BCE_DIR,
    MODEL_ZLPR_DIR,
    ONNX_ASL_PATH,
    ONNX_BCE_PATH,
    ONNX_DIR,
    ONNX_ZLPR_PATH,
)

# (name, pytorch_dir, onnx_path)
_EXPORT_REGISTRY: list[tuple[str, str, str]] = [
    ("BCE", MODEL_BCE_DIR, ONNX_BCE_PATH),
    ("ASL", MODEL_ASL_DIR, ONNX_ASL_PATH),
    ("ZLPR", MODEL_ZLPR_DIR, ONNX_ZLPR_PATH),
]


def export_model_to_onnx(
    model_dir: str,
    onnx_path: str,
    max_length: int = MAX_LENGTH,
    opset_version: int = 17,
) -> None:
    """Export a single model to ONNX and validate output.

    Args:
        model_dir: Path to the PyTorch model directory.
        onnx_path: Output ONNX file path.
        max_length: Maximum sequence length for dummy input.
        opset_version: ONNX opset version.
    """
    import onnx
    import onnxruntime as ort

    # Load model
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model.eval()

    # Create dummy input
    dummy_text = "Đây là câu test cho việc export model"
    dummy_input = tokenizer(
        dummy_text,
        padding="max_length",
        truncation=True,
        max_length=max_length,
        return_tensors="pt",
    )
    input_ids = dummy_input["input_ids"]
    attention_mask = dummy_input["attention_mask"]

    # Export
    dynamic_axes = {
        "input_ids": {0: "batch_size", 1: "sequence_length"},
        "attention_mask": {0: "batch_size", 1: "sequence_length"},
        "logits": {0: "batch_size"},
    }

    # Suppress trace dict warning
    model.config.return_dict = False

    torch.onnx.export(
        model,
        (input_ids, attention_mask),
        onnx_path,
        opset_version=opset_version,
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes=dynamic_axes,
    )

    # Restore config
    model.config.return_dict = True

    # Validate ONNX model
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)

    # Compare outputs
    with torch.no_grad():
        pt_output = model(input_ids=input_ids, attention_mask=attention_mask)
        pt_logits = pt_output.logits.numpy()

    session = ort.InferenceSession(onnx_path)
    ort_logits = session.run(
        None,
        {
            "input_ids": input_ids.numpy(),
            "attention_mask": attention_mask.numpy(),
        },
    )[0]

    max_diff = np.max(np.abs(pt_logits - ort_logits))
    print(f"    Max output diff (PyTorch vs ONNX): {max_diff:.6e}")
    if max_diff > 1e-4:
        print(f"    ⚠ Warning: output difference exceeds threshold!")
    else:
        print(f"    ✓ Output validated successfully")


def main() -> None:
    os.makedirs(ONNX_DIR, exist_ok=True)

    print("=" * 60)
    print("ONNX EXPORT")
    print("=" * 60)

    for name, model_dir, onnx_path in _EXPORT_REGISTRY:
        if not os.path.exists(os.path.join(model_dir, "config.json")):
            print(f"\n  ⚠ Skipping {name}: model not found at {model_dir}")
            continue

        print(f"\n  Exporting {name} → {onnx_path}")
        export_model_to_onnx(model_dir, onnx_path)
        file_size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
        print(f"    Size: {file_size_mb:.1f} MB")

    print(f"\n  All ONNX models saved to: {ONNX_DIR}")
    print("\nDone!")


if __name__ == "__main__":
    main()
