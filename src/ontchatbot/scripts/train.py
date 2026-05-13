"""Fine-tune PhoBERT for token-level NER on the academic-procedure corpus.

Pipeline (in ``main``):
    train → save_model → ONNX(FP32, intermediate) → parity check vs PyTorch
          → dynamic INT8 quantization → ONNX(INT8, deployment artifact)
          → (optional) push to HF Hub

The deployment artifact is **only** the INT8 ``model.onnx`` (single self-
contained file, ~130 MB). The FP32 intermediate (``model_fp32.onnx`` +
external data) exists transiently to anchor the strict parity check and is
deleted before push.

Outputs:
    - ``models/phobert_ner_ft/``                best checkpoint + tokenizer + INT8 ONNX
    - ``artifacts/training/log_history.json``
    - ``artifacts/training/training_curves.png``  train loss / val loss / accuracy / F1-macro
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from seqeval.metrics import accuracy_score, f1_score, precision_score, recall_score
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
    set_seed,
)

from ..config import (
    BATCH_SIZE,
    EPOCHS,
    FINETUNED_MODEL_NAME,
    LEARNING_RATE,
    MAX_LENGTH,
    MODEL_DIR,
    MODEL_NAME,
    SEED,
    CHECKPOINT_DIR,
    TRAIN_ARTIFACTS_DIR,
    TRAIN_PATH,
    VAL_SIZE,
)
from ..ner_model import NerModel
from ..viz.training_curves import plot_training_curves


def _build_compute_metrics(i2l: dict[int, str]):
    def _compute(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        true_seqs, pred_seqs = [], []
        for p_row, l_row in zip(preds, labels):
            t_seq, p_seq = [], []
            for p, l in zip(p_row, l_row):
                if l == -100:
                    continue
                t_seq.append(i2l[int(l)])
                p_seq.append(i2l[int(p)])
            true_seqs.append(t_seq)
            pred_seqs.append(p_seq)
        return {
            "accuracy": accuracy_score(true_seqs, pred_seqs),
            "precision_macro": precision_score(true_seqs, pred_seqs, average="macro", zero_division=0),
            "recall_macro": recall_score(true_seqs, pred_seqs, average="macro", zero_division=0),
            "f1_macro": f1_score(true_seqs, pred_seqs, average="macro", zero_division=0),
            "f1_micro": f1_score(true_seqs, pred_seqs, average="micro", zero_division=0),
        }
    return _compute


def _export_to_onnx(model_dir: Path) -> Path:
    """Convert fine-tuned PyTorch weights → FP32 ONNX (intermediate).

    Writes to ``model_fp32.onnx`` rather than ``model.onnx`` because the
    final deployment artifact is the INT8 quantization downstream — the
    FP32 file is just the anchor for the strict parity check. Returns the
    path of the FP32 file so the caller can chain into quantization.

    Uses the dynamo path (default in torch 2.6+) with ``onnxscript`` as the
    op translator. The legacy TorchScript exporter does **not** work on
    transformers ≥ 4.50 because the masking utilities call ``torch.export``-
    style shape APIs that only resolve under ``torch.export.export`` —
    exactly what dynamo uses internally.

    ``dynamic_shapes`` declares ``batch`` and ``seq`` as varying dims so
    the same ``.onnx`` file serves any input length up to ``MAX_LENGTH``.
    Opset 18 is the minimum compatible with the dynamo translator and is
    fully supported by onnxruntime 1.16+.
    """
    from torch.export import Dim

    print(f"[export] converting → FP32 ONNX at {model_dir}")
    model = AutoModelForTokenClassification.from_pretrained(str(model_dir)).to("cpu")
    model.eval()

    # Dummy inputs: shape doesn't matter since batch+seq are dynamic; values
    # just need to be valid token ids. seq=4 ≥ ``seq`` Dim min.
    dummy_ids = torch.tensor([[0, 1, 2, 2]], dtype=torch.long)
    dummy_mask = torch.ones_like(dummy_ids)

    batch = Dim("batch")
    seq = Dim("seq", min=2, max=MAX_LENGTH)
    dynamic_shapes = {
        "input_ids":      {0: batch, 1: seq},
        "attention_mask": {0: batch, 1: seq},
    }

    fp32_path = model_dir / "model_fp32.onnx"
    torch.onnx.export(
        model,
        (dummy_ids, dummy_mask),
        str(fp32_path),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_shapes=dynamic_shapes,
        opset_version=18,
        dynamo=True,
        verbose=False,
    )
    if not fp32_path.exists():
        raise RuntimeError(
            f"torch.onnx.export returned without error but {fp32_path} missing"
        )
    size_mb = fp32_path.stat().st_size / 1024 / 1024
    print(f"[export] wrote {fp32_path} ({size_mb:.1f} MB)")
    return fp32_path


def _verify_onnx_parity(model_dir: Path, onnx_path: Path) -> None:
    """Run a sample through PyTorch + ONNX; assert logits ≈ and argmax identical.

    Strict tolerance (1e-3) is calibrated for the FP32 ONNX: it absorbs
    rounding from graph reordering but flags a real bug. **Do not call
    this on a quantized ONNX** — INT8 weights shift logits by far more
    than 1e-3 even when the model is fine.

    Fails loudly with the observed diff so a botched export does not ship.
    """
    import onnxruntime as ort

    print(f"[verify] PyTorch ⇄ ONNX parity check on {onnx_path.name}")
    pt = AutoModelForTokenClassification.from_pretrained(str(model_dir)).to("cpu")
    pt.eval()
    session = ort.InferenceSession(
        str(onnx_path),
        providers=["CPUExecutionProvider"],
    )

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    encode = NerModel.make_encoder(tokenizer, MAX_LENGTH)
    sample_words = ["xin", "chào", "phòng", "đào_tạo", "cho", "hỏi"]
    input_ids, _ = encode(sample_words)
    ids_t = torch.tensor([input_ids], dtype=torch.long)
    mask_t = torch.ones_like(ids_t)

    with torch.no_grad():
        pt_logits = pt(input_ids=ids_t, attention_mask=mask_t).logits

    ort_outputs = session.run(
        None,
        {"input_ids": ids_t.numpy(), "attention_mask": mask_t.numpy()},
    )
    ort_logits = torch.from_numpy(ort_outputs[0])

    diff = (pt_logits - ort_logits).abs().max().item()
    pt_pred = pt_logits.argmax(dim=-1)
    ort_pred = ort_logits.argmax(dim=-1)
    argmax_eq = torch.equal(pt_pred, ort_pred)

    print(f"[verify] max abs logit diff = {diff:.6e}")
    print(f"[verify] argmax identical    = {argmax_eq}")
    if diff > 1e-3:
        raise RuntimeError(
            f"ONNX parity check FAILED: logit diff {diff:.6e} > 1e-3. "
            f"Refusing to ship a model whose ONNX output drifts from PyTorch."
        )
    if not argmax_eq:
        raise RuntimeError(
            "ONNX parity check FAILED: PyTorch and ONNX disagree on argmax. "
            "BIO tag predictions would diverge in production."
        )
    print("[verify] OK — ONNX matches PyTorch within tolerance")


def _quantize_to_int8(src: Path, dst: Path) -> None:
    """Dynamic INT8 quantization — replaces FP32 ONNX as the deployment artifact.

    Dynamic quantization is the standard for transformer encoders: weights
    drop to int8 (4× compression, ~537 MB → ~130 MB), activations stay FP32
    so no calibration data is needed, and ORT runs int8 MatMul kernels on
    CPU (~1.5–3× faster at this size). Output is a single self-contained
    file under 2 GB — eliminates the protobuf-external-data machinery
    entirely, which is what bit us in production before.

    Accuracy impact is small (~0.3–0.5% F1 typical for BERT-family); the
    operator should still smoke-test by hitting /chat with a few queries
    before considering the new model production-ready.
    """
    from onnxruntime.quantization import quantize_dynamic, QuantType

    print(f"[quantize] {src.name} → {dst.name} (dynamic INT8)")
    quantize_dynamic(
        model_input=str(src),
        model_output=str(dst),
        weight_type=QuantType.QInt8,
    )
    if not dst.exists():
        raise RuntimeError(
            f"quantize_dynamic returned without error but {dst} missing"
        )
    size_mb = dst.stat().st_size / 1024 / 1024
    print(f"[quantize] wrote {dst} ({size_mb:.1f} MB)")


def _push_to_hub(model_dir: Path, repo_id: str) -> None:
    """Upload entire ``model_dir`` to HF Hub at ``repo_id``.

    Auth: expects ``huggingface-cli login`` to have been run once, or env
    ``HF_TOKEN`` to be set. ``HfApi`` reads either source automatically.
    """
    from huggingface_hub import HfApi

    api = HfApi()
    print(f"[push] ensuring repo {repo_id} exists")
    api.create_repo(repo_id, exist_ok=True, private=False)
    print(f"[push] uploading {model_dir} → {repo_id}")
    api.upload_folder(
        folder_path=str(model_dir),
        repo_id=repo_id,
        commit_message=(
            f"Fine-tuned PhoBERT NER (epochs={EPOCHS}, lr={LEARNING_RATE})"
        ),
    )
    print(f"[push] done → https://huggingface.co/{repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--push", default=False, nargs="?", const=FINETUNED_MODEL_NAME,
        help=("After training + ONNX export, upload the full MODEL_DIR to HF Hub"
              f"Requires `huggingface-cli login` or HF_TOKEN env var."),
    )
    cli_args = parser.parse_args()

    set_seed(SEED)
    labels, l2i, i2l = NerModel.label_mappings()

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_fast=True)
    full = NerModel.load_split(TRAIN_PATH, l2i)
    split = full.train_test_split(test_size=VAL_SIZE, seed=SEED)
    tok_fn = NerModel.make_tokenize_fn(tokenizer)
    train_ds = split["train"].map(tok_fn, batched=True, remove_columns=split["train"].column_names)
    val_ds = split["test"].map(tok_fn, batched=True, remove_columns=split["test"].column_names)

    model = AutoModelForTokenClassification.from_pretrained(
        MODEL_NAME, num_labels=len(labels), id2label=i2l, label2id=l2i,
    )

    args = TrainingArguments(
        output_dir=str(CHECKPOINT_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        optim="adamw_torch_fused" if torch.cuda.is_available() else "adamw_torch",
        learning_rate=LEARNING_RATE,
        weight_decay=0.005,
        warmup_steps=0.1,
        eval_strategy="steps",
        eval_steps=50,
        save_strategy="steps",
        save_steps=50,
        logging_strategy="steps",
        logging_steps=50,
        report_to="none",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        seed=SEED,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=_build_compute_metrics(i2l),
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )
    trainer.train()
    trainer.save_model(str(MODEL_DIR))
    tokenizer.save_pretrained(str(MODEL_DIR))

    ARTIFACTS_DIR = Path(TRAIN_ARTIFACTS_DIR)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS_DIR / "log_history.json").write_text(
        json.dumps(trainer.state.log_history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    plot_training_curves(trainer.state.log_history, str(ARTIFACTS_DIR / "training_curves.png"))

    # ONNX export pipeline: FP32 export → parity check vs PyTorch → INT8
    # quantization → cleanup FP32 intermediates → optionally push. The strict
    # parity check runs on FP32 (where 1e-3 tolerance is meaningful) BEFORE
    # quantization; INT8 ships only after the FP32 anchor passed.
    model_path = Path(MODEL_DIR)
    fp32_path = _export_to_onnx(model_path)
    _verify_onnx_parity(model_path, fp32_path)
    int8_path = model_path / "model.onnx"
    _quantize_to_int8(fp32_path, int8_path)
    # The FP32 ONNX + its external-data sidecar were only needed to anchor
    # the parity check; deleting them keeps MODEL_DIR (and the eventual HF
    # Hub push) free of the larger, fragile FP32 artifact.
    fp32_path.unlink(missing_ok=True)
    (model_path / "model_fp32.onnx.data").unlink(missing_ok=True)
    if cli_args.push:
        _push_to_hub(model_path, cli_args.push)


if __name__ == "__main__":
    main()
