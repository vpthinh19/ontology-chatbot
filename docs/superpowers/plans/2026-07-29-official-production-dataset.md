# Official Production Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the stale ontology-coupled dataset and PhoBERT gate with one validated dataset that trains a seq2seq model to emit executable SPARQL or `không có thông tin`.

**Architecture:** A small query catalogue declares each supported query family and its typed slots. The three JSONL splits keep raw Vietnamese questions and instantiated one-line targets; shared validation checks catalogue conformance, ontology execution, slot coverage, preprocessing leakage, and the rejection marker. Question writing remains curated, while code is limited to validation, reporting, deterministic assembly, and checksums.

**Tech Stack:** Python 3.12, RDFLib 7.6, pytest 9, JSON Lines, Turtle, existing Transformers/CTranslate2 interfaces.

## Global Constraints

- Production uses one seq2seq model and no separate domain gate.
- Model output is exactly one one-line SPARQL `SELECT` or `không có thông tin`.
- Academic procedures are the primary domain; tuition/payment, forms, numeric academic rules, and certificate conversion are secondary domains.
- Chapter/article/clause/point resources are provenance only, not standalone user-facing query targets.
- Dataset rows keep exactly `id`, `query_id`, `register`, `input`, and `target`; do not add `origin` or normalized text.
- Store raw user wording; call the same `normalize_model_input` in training, evaluation, and runtime.
- Preprocessing expands only whole-token, deterministic abbreviations and never resolves IRI, intent, or SPARQL.
- Train contains every production IRI, operator, query shape, and rejection class; validation/test hold out wording, not ontology schema.
- Scripted tooling may validate, assemble, count, and checksum data, but must not synthesize bulk question prose.
- Do not fine-tune, tune hyperparameters, or regenerate benchmark figures in this plan.
- Preserve unrelated user files and never add a `Co-authored-by` trailer.

---

## File structure

- `src/ontchatbot/runtime/pipeline.py`: one-model orchestration and marker handling.
- `src/ontchatbot/runtime/text.py`: deterministic normalization shared by all paths.
- `src/ontchatbot/research/catalogue.py`: catalogue loading, template matching, and typed slot extraction.
- `src/ontchatbot/research/dataset.py`: split-level and release-level validation.
- `src/ontchatbot/research/benchmark.py`: held-out contract that accepts SPARQL and marker targets.
- `src/ontchatbot/research/evaluation.py`: separate in-domain and rejection metrics.
- `src/ontchatbot/research/reporting.py`: public dataset distribution and checksum report.
- `resources/dataset/main/catalogue.jsonl`: supported query-family contract.
- `resources/dataset/main/{train,val,test}.jsonl`: released examples.
- `resources/dataset/main/manifest.json`: generated counts and SHA-256 values.
- `resources/cases/user_queries.txt`: real-user regression inputs, not automatically loaded as training data.
- `resources/cases/rejection_checklist.json`: review-only mapping from rejection class to released row IDs; it is not a model input field.
- `tests/research/test_catalogue.py`: catalogue template unit tests.
- `tests/research/test_dataset.py`: dataset and split contract unit tests.
- `tests/research/test_dataset_content.py`: canonical release coverage tests.

### Task 1: Remove the separate gate from production

**Files:**
- Modify: `src/ontchatbot/runtime/pipeline.py`
- Modify: `src/ontchatbot/runtime/api.py`
- Modify: `src/ontchatbot/cli/serve.py`
- Modify: `src/ontchatbot/settings.py`
- Modify: `pyproject.toml`
- Modify: `tests/runtime/test_inference.py`
- Modify: `tests/runtime/test_serve_cli.py`
- Modify: `tests/runtime/test_serve.py`
- Delete: `src/ontchatbot/runtime/gate.py`
- Delete: `src/ontchatbot/research/gate_dataset.py`
- Delete: `src/ontchatbot/research/gate_evaluation.py`
- Delete: `src/ontchatbot/research/gate_training.py`
- Delete: `src/ontchatbot/research/evaluate_gate_ctranslate2.py`
- Delete: `src/ontchatbot/tools/gate_conversion.py`
- Delete: `src/ontchatbot/cli/convert_gate.py`
- Delete: `src/ontchatbot/cli/evaluate_gate_ct2.py`
- Delete: `src/ontchatbot/cli/train_gate.py`
- Delete: `src/ontchatbot/cli/validate_gate_data.py`
- Delete: `tests/runtime/test_gate.py`
- Delete: `tests/research/test_gate_dataset.py`
- Delete: `tests/research/test_gate_evaluation.py`
- Delete: `tests/research/test_gate_training.py`
- Delete: `tests/research/test_gate_ctranslate2.py`
- Delete: `tests/research/test_gate_release.py`
- Delete: `tests/tools/test_gate_conversion.py`

**Interfaces:**
- Consumes: `QueryGenerator.generate(text: str) -> str`, `NO_INFORMATION_REPLY`.
- Produces: `OntologyChatbot(generator: QueryGenerator, graph: Graph | None = None)` whose `answer()` handles both model outputs.

- [x] **Step 1: Rewrite runtime tests for the one-model contract**

Add tests equivalent to:

```python
def test_model_marker_returns_no_information(graph):
    generator = SimpleNamespace(generate=lambda _: "không có thông tin")
    assert OntologyChatbot(generator, graph).answer("xin chào") == "Không có thông tin."


def test_select_output_executes_without_gate(graph):
    generator = SimpleNamespace(generate=lambda _: VALID_QUERY)
    assert "Phòng" in OntologyChatbot(generator, graph).answer("nộp ở đâu")
```

Update CLI tests so `serve_sparql --model-dir model` is sufficient and
`--gate-model-dir` is rejected.

- [x] **Step 2: Run the focused tests and confirm the old API fails**

Run: `uv run pytest tests/runtime/test_inference.py tests/runtime/test_serve.py tests/runtime/test_serve_cli.py -q`

Expected: FAIL because `OntologyChatbot` still requires `gate` and the CLI still requires `--gate-model-dir`.

- [x] **Step 3: Implement marker dispatch and remove gate loading**

Use a module constant for the model marker and branch before SPARQL validation:

```python
NO_INFORMATION_TARGET = "không có thông tin"

output = self.generator.generate(question).strip()
if output == NO_INFORMATION_TARGET:
    return NO_INFORMATION_REPLY
rows = execute_select(self.graph, output)
return render_rows(rows)
```

Keep trace logging for raw input, normalized input, exact model output, ontology row count, reply, failure stage, and timings. Remove `OutOfScopeError`, `DomainGate`, gate probability, threshold, gate environment variables, gate CLI entry points, and all gate-only modules/tests/resources listed above.

- [x] **Step 4: Run runtime and import verification**

Run: `uv run pytest tests/runtime -q`

Run: `rg -n "DomainGate|PhoBERT|GATE_DIR|gate-model-dir|domain_gate" src pyproject.toml tests -g '!**/__pycache__/**'`

Expected: runtime tests PASS; `rg` returns no active-code match.

- [x] **Step 5: Commit the one-model runtime**

```bash
git add pyproject.toml src/ontchatbot tests/runtime tests/research tests/tools
git commit -m "Remove the separate domain gate"
```

### Task 2: Harden shared Vietnamese preprocessing

**Files:**
- Modify: `src/ontchatbot/runtime/text.py`
- Modify: `tests/runtime/test_model_text.py`
- Test reference only: `test_preprocess.py`

**Interfaces:**
- Consumes: raw arbitrary Unicode text.
- Produces: `normalize_model_input(text: str) -> str`, deterministic and idempotent.

- [x] **Step 1: Add regression tests from real user wording**

Cover at least these exact expectations:

```python
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("đóng tiền hp sao", "đóng tiền học phần sao"),
        ("tui rớt môn rồi, hc lại sao giờ", "tui rớt môn rồi, học lại sao giờ"),
        ("làm sao bảo lưu, tui sắp đi nvqs", "làm sao bảo lưu, tui sắp đi nghĩa vụ quân sự"),
        ("sv đkhp 3tc", "sinh viên đăng ký học phần 3 tín chỉ"),
        ("hpk65", "hpk65"),
        ("timestamp svx hcmc", "timestamp svx hcmc"),
    ],
)
def test_real_input_normalization(source, expected):
    assert normalize_model_input(source) == expected
```

Also assert idempotence for every case and verify `k65`/`khoa65` become `khoá 65` without interpreting arbitrary letter-number IDs.

- [x] **Step 2: Run normalization tests before editing**

Run: `uv run pytest tests/runtime/test_model_text.py -q`

Expected: at least the new compact-token case fails.

- [x] **Step 3: Implement only confirmed normalization rules**

Retain the explicit user decision `hp → học phần`. Port only useful behavior from `test_preprocess.py`: repeated-character cleanup for known chat tokens and safe cohort/credit forms. Do not port URL removal, alias matching, intent detection, word segmentation, or fuzzy normalization. Keep whole-token matching and document every retained one-character mapping in the test table.

- [x] **Step 4: Verify normalizer parity across code paths**

Run: `rg -n "normalize_model_input" src/ontchatbot/research src/ontchatbot/runtime`

Run: `uv run pytest tests/runtime/test_model_text.py tests/runtime/test_inference.py tests/tools/test_model_tokenizers.py -q`

Expected: all tests PASS; trainer, Transformers evaluator, CTranslate2 evaluator, runtime model, pipeline, benchmark, and reporting import the same function.

- [x] **Step 5: Commit preprocessing**

```bash
git add src/ontchatbot/runtime/text.py tests/runtime/test_model_text.py
git commit -m "Harden Vietnamese input normalization"
```

### Task 3: Add a typed query catalogue

**Files:**
- Create: `src/ontchatbot/research/catalogue.py`
- Create: `tests/research/test_catalogue.py`
- Modify: `src/ontchatbot/settings.py`

**Interfaces:**
- Produces: `SlotSpec`, `QuerySpec`, `load_catalogue(path: Path) -> dict[str, QuerySpec]`, `match_target(spec: QuerySpec, target: str) -> dict[str, str] | None`.
- Catalogue path: `QUERY_CATALOGUE_PATH = DATASET_DIR / "catalogue.jsonl"`.

- [x] **Step 1: Write tests for static, IRI-slot, numeric-slot, and repeated-slot templates**

Use catalogue records shaped as:

```json
{"query_id":"procedure-instruction","domain":"procedure","target_template":"SELECT ?answer WHERE { ${procedure} :instructionProvision ?part . ?part :officialText ?answer . }","slots":{"procedure":{"kind":"iri","values":[":CourseRegistrationProcedure",":CourseRetakeProcedure"]}}}
{"query_id":"performance-band","domain":"academic-rule","target_template":"SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= ${score} && ${score} <= ?maximum) }","slots":{"score":{"kind":"number"}}}
{"query_id":"no-information","domain":"out-of-domain","target_template":"không có thông tin","slots":{}}
```

Tests must reject duplicate `query_id`, unknown domain, missing slot declaration, unused slot, invalid local IRI, finite slot values absent from the template, and a repeated `${score}` that is instantiated with two different numbers.

- [x] **Step 2: Run catalogue tests and confirm the module is absent**

Run: `uv run pytest tests/research/test_catalogue.py -q`

Expected: FAIL with `ModuleNotFoundError: ontchatbot.research.catalogue`.

- [x] **Step 3: Implement strict loading and target matching**

Use immutable dataclasses:

```python
@dataclass(frozen=True)
class SlotSpec:
    kind: Literal["iri", "number"]
    values: tuple[str, ...] = ()


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    domain: Literal["procedure", "tuition", "form", "academic-rule", "certificate", "out-of-domain"]
    target_template: str
    slots: Mapping[str, SlotSpec]
```

Compile `${name}` placeholders with full-string matching. IRI slots accept only declared prefixed names such as `:CourseRetakeProcedure`; number slots accept canonical signed integers/decimals and repeated occurrences use a regex backreference. Marker templates are matched literally.

- [x] **Step 4: Run unit tests**

Run: `uv run pytest tests/research/test_catalogue.py -q`

Expected: PASS.

- [x] **Step 5: Commit catalogue infrastructure**

```bash
git add src/ontchatbot/research/catalogue.py src/ontchatbot/settings.py tests/research/test_catalogue.py
git commit -m "Add the query catalogue contract"
```

### Task 4: Update dataset, benchmark, and metrics contracts

**Files:**
- Modify: `src/ontchatbot/research/dataset.py`
- Modify: `src/ontchatbot/research/benchmark.py`
- Modify: `src/ontchatbot/research/evaluation.py`
- Modify: `tests/research/test_dataset.py`
- Modify: `tests/research/test_benchmark.py`
- Modify: `tests/research/test_evaluation.py`

**Interfaces:**
- Consumes: `dict[str, QuerySpec]` from `load_catalogue`.
- Produces: catalogue-aware `validate_dataset`, `validate_release`, and `validate_benchmark`; evaluation reports with separate `in_domain` and `out_of_domain` sections.

- [x] **Step 1: Replace stale one-target-per-query tests**

Add fixture rows where two different numeric targets both use `query_id="performance-band"`, and marker rows use `query_id="no-information"`. Assert:

```python
assert report["domains"]["out-of-domain"] > 0
assert report["slot_coverage"]["procedure-instruction"]["procedure"]["missing_train"] == []
```

Benchmark tests must allow a held-out numeric target absent verbatim from train when its query family and finite IRI values are supported by train. They must still reject an unknown `query_id`, a target that does not match its template, an unseen finite IRI, and a marker with different spelling.

- [x] **Step 2: Run focused research tests and confirm old assumptions fail**

Run: `uv run pytest tests/research/test_dataset.py tests/research/test_benchmark.py tests/research/test_evaluation.py -q`

Expected: FAIL because the old validator always calls `validate_select`, enforces one target per query ID, and requires verbatim benchmark targets in train.

- [x] **Step 3: Implement catalogue-aware validation**

Change signatures to accept the catalogue explicitly or load the canonical path:

```python
def validate_release(splits, graph, catalogue) -> dict[str, Any]: ...
def validate_benchmark(rows, graph, *, catalogue, training_rows=None) -> dict[str, Any]: ...
```

For each row: resolve `query_id`, match `target_template`, and only parse/execute targets whose domain is not `out-of-domain`. Require every query family in all three splits, all four registers in train per family, two distinct registers in each held-out split, and every finite slot value in train. Restrict near-duplicate rejection to rows sharing a `query_id`; continue rejecting exact normalized duplicates globally.

- [x] **Step 4: Implement marker-aware evaluation**

For marker references, `answer_exact` is exact marker equality and false acceptance means a predicted `SELECT` that validates, executes, and returns rows. For SPARQL references, retain parse rate, execution rate, Result F1, canonical exact, and execution Answer Exact. Return separate `in_domain`, `out_of_domain`, `overall`, `by_register`, and `by_query_id` reports.

- [x] **Step 5: Run focused tests**

Run: `uv run pytest tests/research/test_catalogue.py tests/research/test_dataset.py tests/research/test_benchmark.py tests/research/test_evaluation.py -q`

Expected: PASS.

- [x] **Step 6: Commit contract updates**

```bash
git add src/ontchatbot/research/dataset.py src/ontchatbot/research/benchmark.py src/ontchatbot/research/evaluation.py tests/research/test_dataset.py tests/research/test_benchmark.py tests/research/test_evaluation.py
git commit -m "Validate dynamic SPARQL and rejection targets"
```

### Task 5: Build the procedure query catalogue and dataset core

**Files:**
- Create: `resources/dataset/main/catalogue.jsonl`
- Replace: `resources/dataset/main/train.jsonl`
- Replace: `resources/dataset/main/val.jsonl`
- Replace: `resources/dataset/main/test.jsonl`
- Create: `tests/research/test_dataset_content.py`

**Interfaces:**
- Consumes: the 20 `AcademicProcedure` individuals and their populated edges in `ontology.ttl`.
- Produces: executable procedure query families and independently worded split rows.

- [x] **Step 1: Add release coverage tests before replacing data**

Assert the catalogue contains these procedure families:

```python
PROCEDURE_FAMILIES = {
    "procedure-instruction",
    "procedure-eligibility",
    "procedure-deadline",
    "procedure-result",
    "procedure-submission-office",
    "procedure-review-office",
    "procedure-required-form",
    "procedure-form-download",
    "procedure-overview",
}
```

Assert all 20 procedure IRIs appear in at least one finite catalogue slot and in train, every reference SPARQL executes, every projected value is a literal, and no target directly selects a `Chapter`, `Article`, `Clause`, or `Point` individual.

- [x] **Step 2: Run the new content tests against stale data**

Run: `uv run pytest tests/research/test_dataset_content.py -q`

Expected: FAIL because `catalogue.jsonl` does not exist and old targets reference removed properties.

- [x] **Step 3: Author catalogue entries from populated ontology edges**

Use only procedures for which each edge exists. Templates must follow these canonical shapes:

```sparql
SELECT ?answer WHERE { ${procedure} :instructionProvision ?part . ?part :officialText ?answer . }
SELECT ?answer WHERE { ${procedure} :eligibilityProvision ?part . ?part :officialText ?answer . }
SELECT ?answer WHERE { ${procedure} :deadlineProvision ?part . ?part :officialText ?answer . }
SELECT ?answer WHERE { ${procedure} :resultProvision ?part . ?part :officialText ?answer . }
SELECT ?answer WHERE { ${procedure} :submittedTo ?node . ?node rdfs:label ?answer . }
SELECT ?answer WHERE { ${procedure} :reviewedBy ?node . ?node rdfs:label ?answer . }
SELECT ?answer WHERE { ${procedure} :requiresForm ?node . ?node rdfs:label ?answer . }
SELECT ?answer WHERE { ${procedure} :requiresForm ?form . ?entry :catalogueEntryForForm ?form ; :downloadUrl ?answer . }
```

The overview family may use `OPTIONAL` for populated user-facing fields, but must project only `?instruction`, `?eligibility`, `?deadline`, `?result`, `?office`, `?form`, or `?url`. Do not expose source component labels as answers.

- [x] **Step 4: Curate raw Vietnamese questions across splits**

For every family, train contains all four registers and every finite procedure IRI. Validation/test each contain at least two registers and never repeat a normalized train sentence. Include real patterns such as:

```json
{"id":"question-000001","query_id":"procedure-instruction","register":"colloquial","input":"tui rớt môn rồi, hc lại sao giờ","target":"SELECT ?answer WHERE { :CourseRetakeProcedure :instructionProvision ?part . ?part :officialText ?answer . }"}
{"id":"question-000002","query_id":"procedure-submission-office","register":"noisy","input":"bảo lưu nộp p nào v","target":"SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?node . ?node rdfs:label ?answer . }"}
```

Write each question for its intended split; do not derive validation/test by synonym substitution from a train sentence.

- [x] **Step 5: Validate the procedure-only release**

Run: `uv run validate_sparql_dataset`

Run: `uv run pytest tests/research/test_dataset_content.py tests/ontology/test_sparql_smoke.py -q`

Expected: all targets execute and all 20 procedures are covered; no old `content`, `condition`, `outcome`, `handledBy`, or `receivedBy` target remains.

- [x] **Step 6: Commit the procedure core**

```bash
git add resources/dataset/main/catalogue.jsonl resources/dataset/main/train.jsonl resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl tests/research/test_dataset_content.py
git commit -m "Build the official procedure dataset"
```

### Task 6: Add the four secondary ontology domains

**Files:**
- Modify: `resources/dataset/main/catalogue.jsonl`
- Modify: `resources/dataset/main/train.jsonl`
- Modify: `resources/dataset/main/val.jsonl`
- Modify: `resources/dataset/main/test.jsonl`
- Modify: `tests/research/test_dataset_content.py`

**Interfaces:**
- Consumes: official tuition, payment, form, academic-rule, and certificate individuals.
- Produces: secondary-domain query families with finite IRI coverage and numeric examples.

- [x] **Step 1: Add failing coverage assertions**

Require these families:

```python
SECONDARY_FAMILIES = {
    "tuition-program-cohort-rate",
    "payment-method-list",
    "payment-bank-list",
    "payment-fee",
    "payment-warning",
    "form-list",
    "form-download",
    "academic-performance-band",
    "study-year-band",
    "graduation-classification-band",
    "class-size-rule",
    "language-certificate-level",
    "certificate-criterion",
    "computer-certificate-grade",
}
```

Tests compare finite slot coverage with ontology individuals: all programs referenced by a `TuitionRate`, all 15 language certificates, all 3 computer certificates, and every course category used by a `ClassSizeRule` must occur in train.

- [x] **Step 2: Run content tests and confirm missing families**

Run: `uv run pytest tests/research/test_dataset_content.py -q`

Expected: FAIL listing the absent secondary families.

- [x] **Step 3: Add canonical secondary templates**

Use ontology-tested shapes, including numeric copying:

```sparql
SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= ${score} && ${score} <= ?maximum) }
SELECT ?answer WHERE { ?rule a :CertificateConversionRule ; :appliesToCertificate ${certificate} ; :minimumScore ?minimum ; :maximumScore ?maximum ; :convertedGrade ?answer . FILTER (?minimum <= ${score} && ${score} <= ?maximum) }
SELECT ?answer WHERE { ?rule a :CertificateConversionRule ; :appliesToCertificate ${certificate} ; :mapsToCompetencyLevel ?level ; :criterionText ?answer . }
```

Tuition templates must constrain only combinations represented by `TuitionRate`; form-download templates must traverse `catalogueEntryForForm`; payment answers use labels or literal policy text.

- [x] **Step 4: Curate secondary questions and boundary values**

Cover minimum, maximum, inclusive-boundary, cohort, program alias, certificate abbreviation, and numeric decimal wording. Every finite slot value appears in train. Validation/test use independent wording and numeric values that still produce non-empty results.

- [x] **Step 5: Validate secondary coverage**

Run: `uv run validate_sparql_dataset`

Run: `uv run pytest tests/research/test_dataset_content.py tests/ontology -q`

Expected: PASS with no empty query result and complete finite-slot coverage.

- [x] **Step 6: Commit secondary domains**

```bash
git add resources/dataset/main tests/research/test_dataset_content.py
git commit -m "Cover official secondary ontology domains"
```

### Task 7: Integrate rejection examples and real user cases

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Modify: `resources/dataset/main/val.jsonl`
- Modify: `resources/dataset/main/test.jsonl`
- Modify: `resources/cases/user_queries.txt`
- Create: `resources/cases/rejection_checklist.json`
- Modify: `tests/research/test_dataset_content.py`
- Delete: `resources/dataset/gate/README.md`
- Delete: `resources/dataset/gate/manifest.json`
- Delete: `resources/dataset/gate/train.jsonl`
- Delete: `resources/dataset/gate/val.jsonl`
- Delete: `resources/dataset/gate/test.jsonl`

**Interfaces:**
- Consumes: audited `out_of_scope` questions from the removed gate release and real inputs in `resources/cases/user_queries.txt`/`test.html`.
- Produces: `query_id="no-information"`, `target="không có thông tin"` examples in all splits.

- [x] **Step 1: Add rejection-content tests**

Require all six classes in `rejection_checklist.json`: `greeting-social`, `unrelated`, `near-domain-missing`, `ambiguous`, `nonsensical-noisy`, and `mixed`. Every listed ID must exist in exactly one split and have the marker target; every class must occur in all three splits. Require marker rows in all four registers and between 20% and 35% of each split.

Hard-code regression expectations for the seven current `user_queries.txt` lines after manually assigning each one to SPARQL or marker; a real user query must not be silently omitted.

- [x] **Step 2: Run tests before importing negatives**

Run: `uv run pytest tests/research/test_dataset_content.py -q`

Expected: FAIL because the procedure/secondary release has no marker examples.

- [x] **Step 3: Audit and migrate useful gate negatives**

Read every old `out_of_scope` row while `resources/dataset/gate` is still present. Keep natural, distinct Vietnamese questions; discard machine-like duplicates, malformed fragments with no interpretable intent, and questions now answered by the official ontology. Convert retained rows to the five-field main schema and marker target. Record released row IDs under their review class in `rejection_checklist.json`; do not copy the old binary label or provenance metadata. Delete `resources/dataset/gate` only after all retained rows have been validated in the main release.

- [x] **Step 4: Label real user inputs**

For each line in `resources/cases/user_queries.txt` and each unique chat input extracted from `test.html`, execute the intended query against the new ontology. Assign SPARQL only when it answers the complete request; otherwise assign the marker. Place paraphrase families in one split only to prevent leakage.

- [x] **Step 5: Validate rejection balance and leakage**

Run: `uv run validate_sparql_dataset`

Run: `uv run pytest tests/research/test_dataset.py tests/research/test_dataset_content.py tests/research/test_benchmark.py -q`

Expected: PASS; marker spelling is exact; every split stays within the declared 20–35% rejection range.

- [x] **Step 6: Commit unified in/out-domain data**

```bash
git add resources/dataset/main resources/dataset/gate resources/cases/user_queries.txt resources/cases/rejection_checklist.json tests/research/test_dataset_content.py
git commit -m "Add production rejection and user cases"
```

### Task 8: Synchronize manifest, reports, and public documentation

**Files:**
- Modify: `src/ontchatbot/research/reporting.py`
- Modify: `resources/dataset/main/manifest.json`
- Modify: `resources/dataset/main/README.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/CONCEPT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/TRAINING.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `README.md`
- Modify: `tests/research/test_reporting.py`

**Interfaces:**
- Consumes: validated catalogue/release and canonical ontology.
- Produces: reproducible counts, distributions, SHA-256 checksums, and reader-facing documentation with no stale gate/model-version narrative.

- [x] **Step 1: Write report tests for the new contract**

Assert the public report includes:

```python
assert report["dataset"]["domains"]["procedure"] > 0
assert report["dataset"]["domains"]["out-of-domain"] > 0
assert report["dataset"]["query_families"] == len(catalogue)
assert report["training_readiness"]["finite_slots_missing_from_train"] == []
assert report["sha256"]["catalogue.jsonl"]
```

Remove assumptions that every query ID maps to one target or that only three split files contribute to the release checksum.

- [x] **Step 2: Run reporting tests and observe stale assumptions**

Run: `uv run pytest tests/research/test_reporting.py -q`

Expected: FAIL until reporting loads the catalogue and marker-aware validation.

- [x] **Step 3: Generate the manifest and public dataset report**

Record exact row counts per split, query-family/domain/register counts, in/out-domain counts, tokenizer round-trip status, ontology SHA-256, and SHA-256 for catalogue/train/val/test. Do not report old benchmark accuracy as if it applied to this dataset.

- [x] **Step 4: Rewrite reader-facing documentation**

Explain in Vietnamese:

```text
tài liệu chính thức → ontology → query catalogue → dataset → model
câu hỏi → preprocessing → model → marker hoặc SPARQL → RDFLib → câu trả lời
```

State that procedures are central, source document nodes are provenance, raw questions are stored before preprocessing, and a single model handles rejection. Remove gate CLI commands, threshold, PhoBERT, stale `215 query`/`2.263 sample` figures, and old ontology properties.

- [x] **Step 5: Verify generated and written material**

Run: `uv run generate_reports`

Run: `uv run pytest tests/research/test_reporting.py -q`

Run: `rg -n "PhoBERT|domain gate|dataset/gate|gate-model-dir|:content|:condition|:outcome|:handledBy|:receivedBy" README.md docs resources/dataset/main -g '!docs/superpowers/**'`

Expected: reporting tests PASS; the final `rg` returns no stale active-contract match.

- [x] **Step 6: Commit synchronized documentation and reports**

```bash
git add src/ontchatbot/research/reporting.py resources/dataset/main README.md docs tests/research/test_reporting.py
git commit -m "Document the official production dataset"
```

### Task 9: Run final static acceptance without training

**Files:**
- Modify only if a failing assertion exposes a defect in files already listed by Tasks 1–8.

**Interfaces:**
- Consumes: complete one-model code, catalogue, dataset, ontology, and docs.
- Produces: evidence that the project is ready for a separate fine-tuning phase.

- [x] **Step 1: Validate the release from its public CLI**

Run: `uv run validate_sparql_dataset`

Expected: exit 0, zero empty SPARQL results, zero missing finite slot values, zero leakage errors.

- [x] **Step 2: Verify tokenizer round trips**

Run: `uv run pytest tests/tools/test_model_tokenizers.py -q`

Expected: all configured model tokenizers round-trip every unique target and marker without `<unk>` corruption.

- [x] **Step 3: Run the complete test suite**

Run: `uv run pytest -q`

Expected: all tests PASS; no expected-failure exemption for stale dataset or gate behavior.

- [x] **Step 4: Check repository hygiene**

Run: `git diff --check`

Run: `git status --short`

Expected: no task-owned uncommitted file; unrelated user-owned files remain untouched and are reported separately.

- [x] **Step 5: Route any defect back to its owning task**

If Steps 1–4 expose a defect, return to the task that owns the affected file,
add a regression test there, repeat that task's focused verification, and use
that task's commit boundary. Do not make an untested acceptance-only edit or an
empty commit.
