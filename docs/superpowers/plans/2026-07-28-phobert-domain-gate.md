# PhoBERT Domain Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Xây một PhoBERT binary classifier chỉ cho model sinh SPARQL xử lý câu hỏi được ontology hiện tại trả lời đầy đủ.

**Architecture:** Dataset gate độc lập với dataset SPARQL và dùng lại câu hỏi hiện có làm positive. Một module research chịu trách nhiệm kiểm tra dữ liệu, huấn luyện, chọn threshold và đánh giá; runtime chỉ nhận giao diện `DomainGate.accepts(text)`. Gate chỉ được nối vào webapp sau khi test đạt đồng thời false acceptance rate không quá 1% và in-scope recall ít nhất 95%.

**Tech Stack:** Python 3.12, PyTorch, Transformers `vinai/phobert-base-v2`, Hugging Face Trainer, pytest, FastAPI.

## Global Constraints

- `in_scope` chỉ áp dụng khi ontology và contract SPARQL hiện tại trả lời đầy đủ toàn bộ câu hỏi.
- Không word-segment; train và inference dùng chung `normalize_model_input`.
- Không cosine similarity, fuzzy matching, luật từ khóa hoặc router theo intent.
- Dataset mỗi dòng có đúng `input` và `label`; ba split nằm ở `resources/gate/`.
- Một seed `42`, dropout mặc định, learning rate `2e-5`, cosine scheduler, `warmup_steps=0.1`, dynamic padding, tối đa 5 epoch.
- Không sửa ontology, dataset SPARQL hoặc benchmark ba model sinh SPARQL.
- Không tích hợp production nếu gate không đạt false acceptance rate ≤ 1% và in-scope recall ≥ 95% trên test.
- Không stage các thay đổi có sẵn của người dùng trong `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `test.html`, `test_phobert.py` hoặc `test_preprocess.py`.

---

### Task 1: Dataset contract and validation

**Files:**
- Create: `src/ontchatbot/research/gate_dataset.py`
- Create: `src/ontchatbot/cli/validate_gate_data.py`
- Modify: `src/ontchatbot/settings.py`
- Modify: `pyproject.toml`
- Test: `tests/research/test_gate_dataset.py`

**Interfaces:**
- Produces: `load_gate_release(path: Path) -> dict[str, list[dict[str, str]]]`
- Produces: `validate_gate_release(release: dict[str, list[dict[str, str]]]) -> dict`
- Produces: `GATE_LABELS = ("in_scope", "out_of_scope")`

- [ ] **Step 1: Write failing contract tests**

Test that valid two-field JSONL loads, and reject extra fields, unknown labels,
empty inputs, duplicate normalized inputs, cross-split normalized duplicates,
class imbalance and train/val/test files that are missing.

- [ ] **Step 2: Verify the tests fail**

Run: `uv run --frozen pytest tests/research/test_gate_dataset.py -q`
Expected: FAIL because `ontchatbot.research.gate_dataset` does not exist.

- [ ] **Step 3: Implement the minimal loader and validator**

Use this public shape:

```python
GATE_LABELS = ("in_scope", "out_of_scope")

def load_gate_release(path: Path) -> dict[str, list[dict[str, str]]]: ...

def validate_gate_release(
    release: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    # {"valid": bool, "splits": ..., "errors": [...]}
    ...
```

The CLI prints the report as UTF-8 JSON and exits nonzero when `valid` is
false. Add `GATE_DIR = RESOURCES / "gate"` and the script
`validate_gate_dataset = "ontchatbot.cli.validate_gate_data:main"`.

- [ ] **Step 4: Run focused and full tests**

Run: `uv run --frozen pytest tests/research/test_gate_dataset.py -q`
Expected: PASS.

Run: `uv run --frozen pytest -q`
Expected: all existing tests remain green.

- [ ] **Step 5: Commit the contract**

```bash
git add pyproject.toml src/ontchatbot/settings.py src/ontchatbot/research/gate_dataset.py src/ontchatbot/cli/validate_gate_data.py tests/research/test_gate_dataset.py
git commit -m "Add domain gate dataset contract"
```

### Task 2: Curated gate dataset

**Files:**
- Create: `resources/gate/train.jsonl`
- Create: `resources/gate/val.jsonl`
- Create: `resources/gate/test.jsonl`
- Create: `resources/gate/README.md`
- Create: `resources/gate/manifest.json`
- Test: `tests/research/test_gate_release.py`

**Interfaces:**
- Consumes: `load_gate_release`, `validate_gate_release`
- Produces: a balanced, immutable three-split gate release

- [ ] **Step 1: Write failing release assertions**

Assert both labels occur equally in every split; all 215 positive `query_id`
families remain represented across the release; every existing SPARQL-dataset
question occurs in the same split with label `in_scope`; and negative family
audits recorded in the manifest pass.

- [ ] **Step 2: Build and review the negative inventory**

Create a review table grouped into `clear_ood`, `near_domain`, and `boundary`.
Distribute every supported negative category across all splits while keeping
exact and punctuation-only variants in one split. Manually compare all
`near_domain` and mixed-request families against the 215 canonical query
targets; any partially answerable mixed request is `out_of_scope`.

- [ ] **Step 3: Write balanced JSONL splits**

Copy every current SPARQL question as `in_scope` in its existing split. Add the
same number of reviewed negatives to that split. Preserve colloquial, noisy,
unaccented and abbreviated forms without word segmentation. Do not generate
negative rows from runtime templates.

- [ ] **Step 4: Generate the manifest and validate**

Record split counts, label counts, category counts and SHA-256 hashes. Run:

```bash
uv run --frozen validate_gate_dataset
uv run --frozen pytest tests/research/test_gate_release.py -q
```

Expected: valid release, equal label counts per split and no cross-split
normalized duplicates.

- [ ] **Step 5: Commit the dataset**

```bash
git add resources/gate tests/research/test_gate_release.py
git commit -m "Add ontology domain gate dataset"
```

### Task 3: Metrics, threshold selection, and training pipeline

**Files:**
- Create: `src/ontchatbot/research/gate_evaluation.py`
- Create: `src/ontchatbot/research/gate_training.py`
- Create: `src/ontchatbot/cli/train_gate.py`
- Test: `tests/research/test_gate_evaluation.py`
- Test: `tests/research/test_gate_training.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `evaluate_gate(labels: list[int], probabilities: list[float], threshold: float) -> dict`
- Produces: `select_threshold(labels: list[int], probabilities: list[float], max_false_acceptance: float = 0.01) -> float`
- Produces: `train_gate(args: argparse.Namespace) -> dict`

- [ ] **Step 1: Write failing metric tests**

Use fixed labels and probabilities to assert confusion counts, in-scope
precision/recall/F1, out-of-scope recall, false acceptance/rejection rates,
ROC-AUC and deterministic threshold selection. Assert threshold selection uses
validation only and maximizes in-scope recall subject to false acceptance ≤ 1%.

- [ ] **Step 2: Implement pure evaluation functions**

Keep metric functions independent of PyTorch so unit tests require no model.
Represent `in_scope` as `1`, use `probability >= threshold` for acceptance and
return all metric names explicitly in a JSON-serializable dictionary.

- [ ] **Step 3: Write failing training configuration tests**

Assert model ID `vinai/phobert-base-v2`, seed 42, maximum 5 epochs, learning
rate `2e-5`, cosine scheduler, `warmup_steps=0.1`, default dropout, dynamic
padding and environment-selected bf16/fp16 are passed to Trainer. Assert raw
inputs go through `normalize_model_input` without word segmentation.

- [ ] **Step 4: Implement training and CLI**

Load `AutoModelForSequenceClassification(..., num_labels=2)`, tokenize to a
maximum of 128 tokens, use `DataCollatorWithPadding`, select the best checkpoint
by validation macro-F1, then select the threshold from validation predictions.
Save `model/`, `metrics.json`, `test_predictions.jsonl`, and a manifest carrying
the threshold and label mapping under `artifacts/models/phobert-gate/`.

- [ ] **Step 5: Run tests and a one-step smoke train**

```bash
uv run --frozen pytest tests/research/test_gate_evaluation.py tests/research/test_gate_training.py -q
uv run --frozen --extra train train_domain_gate --local-files-only --smoke-test
```

Expected: tests pass; smoke artifact loads and returns two logits.

- [ ] **Step 6: Commit training support**

```bash
git add pyproject.toml src/ontchatbot/research/gate_evaluation.py src/ontchatbot/research/gate_training.py src/ontchatbot/cli/train_gate.py tests/research/test_gate_evaluation.py tests/research/test_gate_training.py
git commit -m "Add PhoBERT domain gate training"
```

### Task 4: Full training and independent evaluation

**Files:**
- Create: `artifacts/models/phobert-gate/` (ignored runtime artifact)
- Create: `reports/gate.json`
- Create: `reports/figures/gate-confusion-matrix.svg`
- Create: `reports/figures/gate-probability-distribution.svg`
- Create: `reports/figures/gate-roc-pr.svg`
- Modify: `src/ontchatbot/research/reporting.py`
- Test: `tests/research/test_gate_reporting.py`

**Interfaces:**
- Consumes: approved gate dataset and training CLI
- Produces: tested model, calibrated threshold and public benchmark figures

- [ ] **Step 1: Fine-tune exactly once**

```bash
uv run --frozen --extra train train_domain_gate --local-files-only --save-model
```

Do not launch seed sweeps or hyperparameter searches. Retain only the selected
checkpoint and final model.

- [ ] **Step 2: Evaluate untouched test split**

Use the threshold selected from validation. Write test probabilities and all
specified metrics without changing the threshold. Measure warm model latency
on CPU and peak VRAM during training.

- [ ] **Step 3: Enforce deployment criteria**

Set `deployment_ready=true` only when test false acceptance rate ≤ 0.01 and
test in-scope recall ≥ 0.95. Otherwise stop before Task 5 and report the exact
error categories; do not tune against test.

- [ ] **Step 4: Generate and test deterministic figures**

Add reporting tests asserting the three SVG files exist, contain Vietnamese
titles and derive their values from `reports/gate.json`.

- [ ] **Step 5: Commit reproducible reports, not model weights**

```bash
git add reports/gate.json reports/figures/gate-*.svg src/ontchatbot/research/reporting.py tests/research/test_gate_reporting.py
git commit -m "Publish PhoBERT gate evaluation"
```

### Task 5: Runtime integration after quality gate passes

**Files:**
- Create: `src/ontchatbot/runtime/gate.py`
- Modify: `src/ontchatbot/runtime/pipeline.py`
- Modify: `src/ontchatbot/runtime/api.py`
- Modify: `src/ontchatbot/cli/serve.py`
- Modify: `pyproject.toml`
- Test: `tests/runtime/test_gate.py`
- Test: `tests/runtime/test_inference.py`
- Test: `tests/runtime/test_serve.py`

**Interfaces:**
- Produces: `GateDecision(accepted: bool, probability: float)`
- Produces: `DomainGate.decide(text: str) -> GateDecision`
- Produces: `OutOfScopeError`

- [ ] **Step 1: Write failing unit and API tests**

Assert rejected input never calls `QueryGenerator.generate`; accepted input
keeps the current path unchanged; `/chat` returns a stable Vietnamese scope
message for rejection; and model load reads threshold and label mapping from
the gate manifest rather than hard-coding them.

- [ ] **Step 2: Implement the minimal PyTorch gate**

Load the fine-tuned tokenizer and `AutoModelForSequenceClassification` once at
startup, call `normalize_model_input`, apply softmax to the `in_scope` logit and
compare it with the stored threshold. Do not expose classifier internals to the
pipeline.

- [ ] **Step 3: Wire the optional gate into the service**

Add required `--gate-model-dir` when serving the production chatbot. Construct
`OntologyChatbot(generator, gate=gate)` and map `OutOfScopeError` to a normal
chat reply rather than an invalid-SPARQL error.

- [ ] **Step 4: Resolve production dependencies without touching unrelated lock changes**

Add only the runtime packages required to load PhoBERT. Regenerate the lock in
a controlled commit after preserving the user's existing lockfile changes;
review the diff and stage only changes attributable to the gate.

- [ ] **Step 5: Run full runtime verification**

```bash
uv run --frozen pytest tests/runtime -q
uv run --frozen pytest -q
```

Start the service with both artifacts and manually verify known in-scope,
clear OOD, near-domain OOD, noisy positive and mixed-request cases.

- [ ] **Step 6: Commit runtime integration**

```bash
git add pyproject.toml src/ontchatbot/runtime/gate.py src/ontchatbot/runtime/pipeline.py src/ontchatbot/runtime/api.py src/ontchatbot/cli/serve.py tests/runtime
git commit -m "Gate ontology queries with PhoBERT"
```

### Task 6: Public documentation and final verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/TRAINING.md`
- Modify: `docs/DEPLOYMENT.md`

**Interfaces:**
- Consumes: verified gate report and runtime contract
- Produces: public Vietnamese explanation of the production pipeline

- [ ] **Step 1: Document the user-visible architecture**

Add a Mermaid flow showing PhoBERT rejection before SPARQL generation. Explain
the two labels, dataset distribution, threshold policy, benchmark metrics,
hardware, commands and deployment without exposing development-stage history.

- [ ] **Step 2: Add figures and benchmark interpretation**

Embed the confusion matrix, probability distribution and ROC/PR figure. Lead
with false acceptance and in-scope recall; explain that generator Answer Exact
and gate classification measure different responsibilities.

- [ ] **Step 3: Verify repository state**

```bash
uv run --frozen validate_gate_dataset
uv run --frozen validate_sparql_dataset
uv run --frozen pytest -q
git diff --check
```

Expected: all validators and tests pass, no whitespace errors, and only known
user-owned files remain unstaged.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md docs/ARCHITECTURE.md docs/DATASET.md docs/EVALUATION.md docs/TRAINING.md docs/DEPLOYMENT.md
git commit -m "Document ontology domain gate"
```
