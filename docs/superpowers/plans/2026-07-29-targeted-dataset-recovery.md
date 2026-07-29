# Targeted Dataset Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct evaluation semantics and add only the training examples needed to address the measured T5Gemma2 failure clusters.

**Architecture:** Keep the current split boundary and ontology contract. First fix metrics with TDD, then repair the single proven bad label, curate at most 150 new train rows without copying held-out wording, validate every row and tokenizer, and finally run T5Gemma2 once.

**Tech Stack:** Python, pytest, RDFLib, JSONL, Transformers, CUDA.

## Global Constraints

- Do not modify ontology, catalogue schema, preprocessing, tokenizer, model configuration or hyperparameters.
- Do not move existing rows between splits.
- Do not copy validation/test inputs into train.
- Add 100–150 train rows only.
- Do not run BARTpho or ViT5 in this plan.

---

### Task 1: Correct user-visible evaluation metrics

**Files:**
- Modify: `tests/research/test_evaluation.py`
- Modify: `src/ontchatbot/research/evaluation.py`

- [x] Add failing tests for safe empty-result rejection, false rejection and System Answer Exact.
- [x] Implement the minimal counters/rates and error category.
- [x] Run focused evaluation tests.

### Task 2: Repair the proven label defect

**Files:**
- Modify: `resources/dataset/main/test.jsonl`
- Modify: `resources/cases/rejection_checklist.json`
- Modify: `tests/research/test_dataset_content.py`

- [x] Add a failing assertion that `question-002000` is the supported tuition query.
- [x] Replace its target with the canonical Information Technology cohort-65 query and remove it from `ambiguous`.
- [x] Update only the frozen test checksum assertion after semantic validation.

### Task 3: Curate targeted train additions

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Modify: `tests/research/test_dataset_content.py`

- [x] Add 100–120 rows raising weak aggregate/detail families toward 16 train examples.
- [x] Add 20–30 property-contrast and noisy entity-grounding rows.
- [x] Audit every new input/target pair for naturalness, semantics and duplication.

### Task 4: Lock the recovered dataset

**Files:**
- Modify: `resources/dataset/main/manifest.json`
- Modify: `reports/dataset.json`
- Modify: generated dataset figures
- Modify: public dataset documentation

- [x] Run dataset validation, leakage checks and tokenizer audit.
- [x] Generate reports and update generated counts/checksums.
- [x] Run the full test suite and commit the locked dataset.

### Task 5: Run the single T5Gemma2 acceptance experiment

**Files:**
- Replace: `artifacts/models/t5gemma2/`

- [ ] Preserve the current artifact as the before-state, then train T5Gemma2 once from base.
- [ ] Reload the saved artifact independently for validation and test.
- [ ] Compare before/after metrics and stop without tuning or another run.
