"""Fine-tune PhoBERT for token-level NER on the academic-procedure corpus.

Outputs:
    - ``models/phobert_ner_ft/``                best checkpoint, tokenizer, label maps
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


def _export_to_onnx(model_dir: Path) -> None:
    """Convert fine-tuned PyTorch weights → ONNX in-place using optimum.

    Uses ``optimum.exporters.onnx.main_export`` (current API as of optimum
    1.16+). The older pattern ``ORTModel.from_pretrained(..., export=True)``
    is deprecated. ``do_validation=True`` triggers optimum's internal
    atol-based parity check during export; we still run an independent
    check in :func:`_verify_onnx_parity` for visible logging + strict
    argmax equality (which matters for BIO tag prediction).
    """
    from optimum.exporters.onnx import main_export

    print(f"[export] converting → ONNX at {model_dir}")
    main_export(
        model_name_or_path=str(model_dir),
        output=str(model_dir),
        task="token-classification",
        framework="pt",
        do_validation=True,
    )
    onnx_path = model_dir / "model.onnx"
    if not onnx_path.exists():
        raise RuntimeError(
            f"main_export ran without error but {onnx_path} is missing"
        )
    size_mb = onnx_path.stat().st_size / 1024 / 1024
    print(f"[export] wrote {onnx_path} ({size_mb:.1f} MB)")


def _verify_onnx_parity(model_dir: Path) -> None:
    """Run a sample through PyTorch + ONNX; assert logits ≈ and argmax identical.

    Fails loudly with the observed diff so a botched export does not ship.
    A max-abs-diff above 1e-3 indicates numerical drift severe enough to
    risk BIO tag prediction changes — small enough to absorb FP16/FP32
    rounding, big enough to flag a real bug.
    """
    from optimum.onnxruntime import ORTModelForTokenClassification

    print("[verify] loading PyTorch + ONNX checkpoints for parity check")
    pt = AutoModelForTokenClassification.from_pretrained(str(model_dir))
    pt.eval()
    ort = ORTModelForTokenClassification.from_pretrained(str(model_dir))

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    encode = NerModel.make_encoder(tokenizer, MAX_LENGTH)
    sample_words = ["xin", "chào", "phòng", "đào_tạo", "cho", "hỏi"]
    input_ids, _ = encode(sample_words)
    ids_t = torch.tensor([input_ids])
    mask_t = torch.ones_like(ids_t)

    with torch.no_grad():
        pt_logits = pt(input_ids=ids_t, attention_mask=mask_t).logits
    ort_logits = ort(input_ids=ids_t, attention_mask=mask_t).logits

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
        "--push", action="store_true",
        help=("After training + ONNX export, upload the full MODEL_DIR to "
              f"HF Hub at {FINETUNED_MODEL_NAME}. Requires `huggingface-cli "
              "login` or HF_TOKEN env var."),
    )
    args = parser.parse_args()

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
        output_dir=str(MODEL_DIR),
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
        save_total_limit=1,
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

    # ONNX export pipeline: convert → verify parity → optionally push.
    # Verification runs BEFORE push so a broken ONNX never reaches HF Hub.
    model_path = Path(MODEL_DIR)
    _export_to_onnx(model_path)
    _verify_onnx_parity(model_path)
    if args.push:
        _push_to_hub(model_path, FINETUNED_MODEL_NAME)


if __name__ == "__main__":
    main()
