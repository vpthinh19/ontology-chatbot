# CT2 Domain Gate Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize both datasets and deploy the accepted PhoBERT gate with a CTranslate2 INT8 encoder plus its original NumPy classification head.

**Architecture:** Offline conversion exports the PhoBERT encoder through CTranslate2 and the trained two-layer classification head as `classifier.npz`. Runtime loads that single logical gate artifact, rejects out-of-scope input before SPARQL generation, and keeps the existing CT2 generator unchanged.

**Tech Stack:** Python 3.12, CTranslate2 4.8, NumPy, Transformers tokenizer, PyTorch only during offline conversion, pytest, FastAPI.

## Global Constraints

- Dataset paths are exactly `resources/dataset/main/` and `resources/dataset/gate/`; no compatibility copies remain.
- Runtime has no PyTorch or ONNX dependency.
- Gate conversion defaults to INT8 and refuses a non-empty output directory.
- Threshold is loaded from the gate manifest, never hard-coded in runtime.
- CT2+NumPy must preserve the PyTorch test confusion matrix at threshold `0.7527403316567737`.
- Production acceptance is false acceptance ≤ 1.2% and in-scope recall ≥ 95%.
- Do not modify ontology content, dataset content, or the SPARQL generator model.
- Never stage `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `test.html`, `test_phobert.py`, or `test_preprocess.py`.

---

### Task 1: Reorganize dataset resources

**Files:**
- Move: `resources/dataset/*` to `resources/dataset/main/`
- Move: `resources/gate/*` to `resources/dataset/gate/`
- Modify: `src/ontchatbot/settings.py`
- Modify: dataset references in `docs/`, `README.md`, `tests/`, and `src/`

**Interfaces:**
- Produces: `DATASET_DIR = RESOURCES / "dataset" / "main"`
- Produces: `GATE_DIR = RESOURCES / "dataset" / "gate"`

- [ ] Write a failing settings/release test asserting both canonical directories and absence of the old `resources/gate` path.
- [ ] Run `uv run --frozen pytest tests/research/test_dataset.py tests/research/test_gate_release.py -q` and confirm the path assertion fails.
- [ ] Move tracked files with `git mv`, update settings and all literal path references returned by `rg 'resources/(dataset|gate)'`.
- [ ] Run both validators and the full suite; require valid manifests and all tests passing.
- [ ] Commit only the dataset move and path updates as `Reorganize dataset resources`.

### Task 2: Convert the trained gate

**Files:**
- Create: `src/ontchatbot/tools/gate_conversion.py`
- Create: `src/ontchatbot/cli/convert_gate.py`
- Create: `tests/tools/test_gate_conversion.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `convert_gate(source_dir: Path, output_dir: Path, *, quantization: str = "int8") -> dict`
- Produces CLI: `convert_domain_gate --source-dir ... --output-dir ...`

- [ ] Write failing tests using a tiny fake classifier state to assert the four arrays in `classifier.npz`, manifest threshold/labels/checksums, tokenizer copying, and rejection of non-empty output.
- [ ] Run the focused test and confirm import/behavior failure before implementation.
- [ ] Implement conversion with the following boundary: validate
  `source_dir/manifest.json`, convert `source_dir/model` with
  `TransformersConverter`, load `AutoModelForSequenceClassification` offline,
  export float32 head tensors, copy tokenizer files, and write the checksummed
  manifest.

```python
def convert_gate(
    source_dir: Path,
    output_dir: Path,
    *,
    quantization: str = "int8",
) -> dict: ...
```
- [ ] Run focused and full tests.
- [ ] Convert `artifacts/models/phobert-gate-candidate` into a temporary deployment candidate and verify all required files and hashes.
- [ ] Commit conversion code and CLI as `Add CT2 domain gate conversion`.

### Task 3: CT2 gate runtime and parity

**Files:**
- Create: `src/ontchatbot/runtime/gate.py`
- Create: `tests/runtime/test_gate.py`
- Create: `src/ontchatbot/research/evaluate_gate_ctranslate2.py`
- Create: `src/ontchatbot/cli/evaluate_gate_ct2.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `GateDecision(accepted: bool, probability: float)`
- Produces: `DomainGate.decide(text: str) -> GateDecision`
- Produces: `CTranslate2DomainGate.load(model_dir, device="cpu", compute_type="int8")`

- [ ] Write failing runtime tests with a real NumPy head and fake encoder/tokenizer; assert normalization, CLS selection, `dense -> tanh -> out_proj`, stable softmax and manifest threshold.
- [ ] Implement the minimal gate loader and decision path without importing
  torch, using this public result contract:

```python
@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    probability: float
```
- [ ] Write an evaluator that runs the gate dataset test split, reports the existing binary metrics, latency, probability drift and decision differences against PyTorch predictions.
- [ ] Convert the accepted artifact and run full 860-row parity; require identical confusion matrix and accepted production criteria.
- [ ] Promote the candidate to `artifacts/deployment/phobert-gate`, keep only the final CT2 artifact, and commit runtime/evaluator code as `Add CT2 PhoBERT gate runtime`.

### Task 4: Pipeline integration, API, and documentation

**Files:**
- Modify: `src/ontchatbot/runtime/pipeline.py`
- Modify: `src/ontchatbot/runtime/api.py`
- Modify: `src/ontchatbot/cli/serve.py`
- Modify: `tests/runtime/test_inference.py`
- Modify: `tests/runtime/test_serve.py`
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/EVALUATION.md`

**Interfaces:**
- Produces: `OutOfScopeError`
- Changes: `OntologyChatbot(generator, gate, graph=None)`
- Changes CLI: required `--gate-model-dir`

- [ ] Write failing tests proving rejected questions never call the generator, accepted questions follow the existing ontology path, and `/chat` returns HTTP 200 with the stable scope message.
- [ ] Wire `DomainGate` into `OntologyChatbot`, map rejection to the user reply, and load both CT2 artifacts in `serve_sparql` with the same device/compute type.
- [ ] Run focused runtime tests and manually exercise in-scope, clear OOD, near-domain OOD, noisy and mixed requests against the real webapp.
- [ ] Update Vietnamese public documentation, architecture Mermaid, dataset paths, conversion/deployment commands, gate metrics, and CT2+NumPy explanation.
- [ ] Run `validate_gate_dataset`, `validate_sparql_dataset`, full pytest, `git diff --check`, and artifact checksum verification.
- [ ] Commit runtime and docs separately, leaving only known user-owned files unstaged.
