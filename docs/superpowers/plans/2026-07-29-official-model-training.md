# Official Model Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fine-tune and benchmark BARTpho, ViT5 and T5Gemma2 exactly once on the locked 2,000-row ontology dataset, then publish reproducible model reports.

**Architecture:** The tracked dataset manifest is the experiment identity. Each model uses the already-approved common protocol, saves one best Transformers artifact, and is independently reloaded for validation and test evaluation. T5Gemma2 runs first as the acceptance gate; no hyperparameter sweep, multiple seed, CTranslate2 conversion or web testing is allowed in this plan.

**Tech Stack:** PyTorch, Transformers `Seq2SeqTrainer`, RDFLib, CUDA BF16/TF32, pytest.

## Global Constraints

- Dataset manifest SHA-256 must remain `4af505eb03734a0b8a3ee942fc62d93bc1fe64dea50546d7285ff28eeda8ac2b` throughout training.
- Use seed 42 once per model, 20 epochs maximum, early stopping patience 3, learning rate `3e-5`, cosine scheduler, `warmup_steps=0.1`, effective batch 8 and greedy decoding.
- Keep checkpoint-default dropout and do not use `torch.compile`.
- Test never selects a checkpoint or causes a retrain.
- Do not alter ontology, dataset, hyperparameters or training code to improve a score during this run.
- Do not publish stale metrics produced from the former 2,263-row dataset.

---

### Task 1: Freeze the execution inputs

**Files:**
- Verify: `resources/dataset/main/manifest.json`
- Verify: `artifacts/tokenizers/vit5/`
- Test: `tests/tools/test_model_tokenizers.py`
- Test: `tests/research/test_training.py`

**Interfaces:**
- Consumes: locked dataset and three local base-model snapshots.
- Produces: evidence that all model inputs are locally available and tokenizer-safe.

- [x] Run the tokenizer round-trip test for all 2,000 inputs and 482 targets.
- [x] Run the canonical training-protocol unit tests.
- [x] Confirm the manifest checksum, CUDA BF16 support, GPU identity and available disk space.
- [x] Confirm every pre-existing model metric has a different manifest checksum before replacing stale artifacts.

### Task 2: Train and independently evaluate T5Gemma2

**Files:**
- Replace: `artifacts/models/t5gemma2/`

**Interfaces:**
- Consumes: Task 1 preflight and model ID `google/t5gemma-2-270m-270m`.
- Produces: saved best model, `metrics.json`, independent `validation_metrics.json`, `benchmark_metrics.json` and prediction JSONL files.

- [x] Move the three stale model directories out of the canonical output path after proving their manifest mismatch.
- [x] Run `uv run train_sparql --model t5gemma2 --epochs 20 --seed 42 --save-model --local-files-only` once and wait for completion.
- [x] Run `uv run evaluate_sparql_model --model t5gemma2 --model-dir artifacts/models/t5gemma2/model --suite both --output-dir artifacts/models/t5gemma2` once.
- [x] Verify artifact provenance uses the locked manifest and report validation/test System Answer Exact and in-domain Answer Exact.
- [x] If the acceptance target of 90% System Answer Exact is not reached, stop and report errors without tuning or retraining. The independent test result was 79.33%, so Tasks 3–4 remain intentionally pending.

### Task 3: Train and independently evaluate BARTpho and ViT5

**Files:**
- Replace: `artifacts/models/bartpho/`
- Replace: `artifacts/models/vit5/`

**Interfaces:**
- Consumes: accepted Task 2 pipeline and the identical locked dataset/protocol.
- Produces: comparable saved artifacts, metrics and predictions for both remaining models.

- [ ] Train BARTpho once with the same CLI arguments except `--model bartpho`.
- [ ] Independently evaluate BARTpho on validation and test.
- [ ] Train ViT5 once with the same CLI arguments except `--model vit5`.
- [ ] Independently evaluate ViT5 on validation and test.
- [ ] Verify all three training/evaluation reports reference the same manifest checksum and record counts.

### Task 4: Generate and verify the public benchmark

**Files:**
- Create: `reports/models.json`
- Create: `reports/figures/training-loss.svg`
- Create: `reports/figures/validation-curve.svg`
- Create: `reports/figures/model-comparison.svg`
- Create: `reports/figures/test-by-register.svg`
- Create: `reports/figures/test-by-query-feature.svg`
- Modify: `README.md`
- Modify: `docs/TRAINING.md`
- Modify: `docs/EVALUATION.md`

**Interfaces:**
- Consumes: three independently evaluated model artifacts.
- Produces: generated comparison report and Vietnamese public interpretation.

- [ ] Run `uv run generate_reports` and require `models.json` to contain all three models.
- [ ] Add measured hardware, runtime, checkpoint-selection protocol and generated figures to public docs; do not describe development history.
- [ ] Run model-report tests, the full test suite, `git diff --check` and verify the dataset manifest checksum did not change.
- [ ] Commit only tracked source/report/documentation changes; model artifacts remain ignored and no co-author trailer is added.

## Explicitly Deferred

- CTranslate2 conversion and parity testing.
- Web application and UX testing.
- Hyperparameter tuning, multiple seeds or retraining based on test results.
- Ontology or dataset changes.
