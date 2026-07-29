# Official Dataset Curation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biên soạn và nghiệm thu dataset chính thức phủ toàn bộ query catalogue, ngôn ngữ người dùng thực tế và ranh giới từ chối của chatbot ontology.

**Architecture:** Catalogue và ontology sinh ra một contract coverage nhỏ, có thể kiểm tra bằng máy. Ba agent biên soạn các shard trong miền độc lập, agent chính biên soạn OOD và hợp nhất; các agent đổi miền để kiểm tra chéo trước khi tạo ba split chính thức. Chỉ bổ sung code phục vụ coverage, hợp nhất xác định và kiểm định; không tạo câu hỏi hàng loạt bằng script.

**Tech Stack:** Python 3.12, RDFLib 7.6, pytest 9, JSON Lines, Turtle, Git, Fedora Linux.

## Global Constraints

- Nguồn dữ kiện duy nhất là `resources/ontology/ontology.ttl`, `resources/dataset/main/catalogue.jsonl` và tài liệu chính thức đã được ontology dẫn nguồn.
- Model output luôn là một SPARQL `SELECT` canonical trên một dòng hoặc chính xác `không có thông tin`.
- Schema mỗi sample giữ đúng `id`, `query_id`, `register`, `input`, `target`.
- Train phải chứa mọi IRI hữu hạn, operator và dạng SPARQL production; validation/test giữ lại cách diễn đạt, không giữ lại schema.
- Bốn register là `formal`, `neutral`, `colloquial`, `noisy`.
- OOD được tăng theo coverage, không theo tỷ lệ cố định và không được áp đảo dữ liệu trong miền.
- Script chỉ kiểm tra, thống kê, chia/hợp nhất xác định và sinh checksum; không ghép template hoặc từ đồng nghĩa để sinh prose.
- Agent chỉ sửa shard được giao trong `artifacts/dataset-curation/`; không agent nào sửa ontology, catalogue hoặc split chính thức.
- Tác giả không tự duyệt shard của mình.
- Không fine-tune, benchmark, chuyển CTranslate2 hoặc test web trong kế hoạch này.
- Không sửa/stage các thay đổi riêng đang có ở `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py`, `test_preprocess.py`.
- Không thêm trailer `Co-authored-by` vào commit.

---

## File structure

- `resources/dataset/main/coverage.json`: contract coverage số, miền trọng tâm và bảy nhóm từ chối.
- `resources/dataset/main/{train,val,test}.jsonl`: release chính thức sau khi hợp nhất.
- `resources/dataset/main/manifest.json`: số lượng, contract và checksum sinh từ release thật.
- `resources/cases/rejection_checklist.json`: ánh xạ bảy nhóm OOD tới ID chính thức.
- `resources/cases/user_queries.txt`: input người dùng thật dùng cho gán nhãn và hồi quy.
- `src/ontchatbot/research/coverage.py`: đọc contract và đánh giá coverage trên release.
- `src/ontchatbot/research/curation.py`: khởi tạo shard và hợp nhất xác định sang thư mục đích.
- `src/ontchatbot/research/dataset.py`: kiểm tra schema, SPARQL, split, finite slot và leakage hiện có.
- `src/ontchatbot/research/reporting.py`: đưa coverage chính thức vào readiness/report/manifest.
- `src/ontchatbot/cli/validate_data.py`: chạy validation toàn bộ release chính thức.
- `src/ontchatbot/settings.py`: đường dẫn coverage canonical.
- `tests/research/test_coverage.py`: unit test contract và ma trận coverage.
- `tests/research/test_curation.py`: unit test phân shard, đánh ID và remap checklist.
- `tests/research/test_dataset_content.py`: acceptance test của dữ liệu thật.
- `tests/research/test_reporting.py`: readiness, manifest và report chính thức.
- `artifacts/dataset-curation/`: shard và báo cáo review tạm thời, đã bị Git bỏ qua.

### Task 1: Add the machine-checkable coverage contract

**Files:**
- Create: `resources/dataset/main/coverage.json`
- Create: `src/ontchatbot/research/coverage.py`
- Create: `tests/research/test_coverage.py`
- Modify: `src/ontchatbot/settings.py`

**Interfaces:**
- Produces: `CoverageRequirements`, `load_coverage_requirements(path: Path, catalogue: Mapping[str, QuerySpec]) -> CoverageRequirements`.
- Produces: `assess_coverage(splits, catalogue, requirements, rejection_checklist) -> dict[str, object]`.
- Produces: `require_complete_coverage(report: Mapping[str, object]) -> None` raising `CoverageError` on gaps.

- [ ] **Step 1: Write contract parsing tests**

Create fixtures shaped exactly as:

```python
VALID_REQUIREMENTS = {
    "priority_domains": ["procedure"],
    "numeric_cases": [
        {
            "query_id": "academic-performance-band",
            "split": "train",
            "slots": {"score": "4.00"},
        }
    ],
    "rejection_classes": [
        "greeting-social",
        "unrelated",
        "near-domain-missing",
        "ambiguous",
        "noisy-out-of-domain",
        "mixed",
        "hard-negative",
    ],
    "required_registers": ["formal", "neutral", "colloquial", "noisy"],
}
```

Assert rejection of unknown query IDs, non-number slots in `numeric_cases`, unknown splits, duplicate cases/classes and missing required fields.

- [ ] **Step 2: Run the new tests and verify the module is absent**

Run: `uv run pytest tests/research/test_coverage.py -q`

Expected: FAIL because `ontchatbot.research.coverage` does not exist.

- [ ] **Step 3: Implement the minimal immutable contract**

Use these public shapes:

```python
@dataclass(frozen=True)
class NumericCase:
    query_id: str
    split: str
    slots: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class CoverageRequirements:
    priority_domains: tuple[str, ...]
    numeric_cases: tuple[NumericCase, ...]
    rejection_classes: tuple[str, ...]
    required_registers: tuple[str, ...]
```

`assess_coverage` must use `match_target` to compare complete slot assignments, require every catalogue family in every split, require four train registers for every family, require four registers in every split for `priority_domains`, and validate every rejection class across all split/register pairs using the checklist IDs.

- [ ] **Step 4: Create the canonical coverage file**

Declare:

- `priority_domains`: `procedure`;
- all seven rejection classes from `VALID_REQUIREMENTS`;
- all four registers;
- valid ordinary/boundary assignments for the seven numeric query families:
  `tuition-program-cohort-rate`, `academic-performance-band`,
  `study-year-band`, `graduation-classification-band`,
  `language-certificate-level`, `computer-certificate-grade`,
  `tuition-programs-by-rate`.

Use exact values found in the ontology. Include at least every cohort threshold
`63`, `65`, `66`, `67`; every academic/graduation band boundary; every study
year transition `35`, `70`, `105`; every amount mà
`tuition-programs-by-rate` thực sự trả được ngành; and the minimum/maximum
thresholds for every declared certificate family. Các mức học phí khác tiếp
tục được phủ qua query chi tiết học phí tương ứng. Invalid values are OOD cases
and must not be declared as executable numeric targets.

- [ ] **Step 5: Run focused verification**

Run: `uv run pytest tests/research/test_coverage.py tests/research/test_catalogue.py tests/research/test_catalogue_validation.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the coverage contract**

```bash
git add resources/dataset/main/coverage.json src/ontchatbot/research/coverage.py src/ontchatbot/settings.py tests/research/test_coverage.py
git commit -m "Add official dataset coverage contract"
```

### Task 2: Integrate coverage with official validation and reporting

**Files:**
- Modify: `src/ontchatbot/research/reporting.py`
- Modify: `src/ontchatbot/cli/validate_data.py`
- Modify: `tests/research/test_reporting.py`
- Modify: `tests/research/test_dataset_content.py`

**Interfaces:**
- Consumes: `assess_coverage(...)` and `require_complete_coverage(...)` from Task 1.
- Produces: `build_dataset_report(...)["coverage"]` and readiness gaps derived from the same report.
- CLI `validate_sparql_dataset` must fail for incomplete official coverage and print both release and coverage summaries when complete.

- [ ] **Step 1: Write failing readiness and CLI-level tests**

Assert the current 455-row candidate reports:

```python
assert report["coverage"]["complete"] is False
assert report["training_readiness"]["ready"] is False
assert "coverage_incomplete" in {
    gap["code"] for gap in report["training_readiness"]["gaps"]
}
```

Add a fixture release covering all test catalogue requirements and assert `require_complete_coverage` accepts it.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `uv run pytest tests/research/test_reporting.py tests/research/test_dataset_content.py -q`

Expected: FAIL because reports do not load `coverage.json`.

- [ ] **Step 3: Integrate without duplicating dataset validation**

`build_dataset_report` continues to call `validate_release`; then it loads the
coverage contract/checklist and calls `assess_coverage`. Readiness adds one
`coverage_incomplete` gap containing only summary counts, not staging history.
`validate_data.main` calls `require_complete_coverage` after `validate_release`.

- [ ] **Step 4: Include coverage checksum in the manifest**

Add `coverage.json` to `report["sha256"]` and manifest metadata. Do not add
development stages, candidate decisions or agent names to public reports.

- [ ] **Step 5: Run focused verification**

Run: `uv run pytest tests/research/test_coverage.py tests/research/test_reporting.py tests/research/test_dataset_content.py -q`

Expected: PASS while the current candidate remains explicitly not ready.

- [ ] **Step 6: Commit validation integration**

```bash
git add src/ontchatbot/research/reporting.py src/ontchatbot/cli/validate_data.py tests/research/test_reporting.py tests/research/test_dataset_content.py
git commit -m "Enforce official dataset coverage"
```

### Task 3: Add deterministic staging and release assembly

**Files:**
- Create: `src/ontchatbot/research/curation.py`
- Create: `tests/research/test_curation.py`

**Interfaces:**
- Produces: `bootstrap_staging(release, catalogue, staging_dir: Path) -> None`.
- Produces: `assemble_staging(staging_dir: Path) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[str]]]`.
- Domain directories, in fixed order: `procedure`, `tuition-academic-rule`, `certificate-form-document`, `out-of-domain`.

- [ ] **Step 1: Write failing bootstrap and assembly tests**

Use a six-row fixture spanning all domain groups. Assert bootstrap routes rows
by catalogue domain, preserves the five-field row shape, and writes an empty
review directory. Assert assembly:

```python
assert [row["id"] for row in release["train"]] == ["question-000001", "question-000002"]
assert checklist["hard-negative"] == ["question-000002"]
```

Also assert duplicate temporary IDs and checklist IDs absent from OOD rows are rejected.

- [ ] **Step 2: Run tests and verify failure**

Run: `uv run pytest tests/research/test_curation.py -q`

Expected: FAIL because `ontchatbot.research.curation` does not exist.

- [ ] **Step 3: Implement only routing and deterministic assembly**

`bootstrap_staging` writes `train.jsonl`, `val.jsonl`, `test.jsonl` under each
domain directory and copies the current OOD checklist with temporary IDs.
`assemble_staging` sorts by domain order, split order and temporary ID, assigns
global six-digit IDs, and returns a remapped seven-class checklist. It does not
write prose, infer labels or change targets.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/research/test_curation.py tests/research/test_dataset.py -q`

Expected: PASS.

- [ ] **Step 5: Commit assembly support**

```bash
git add src/ontchatbot/research/curation.py tests/research/test_curation.py
git commit -m "Add deterministic dataset curation assembly"
```

### Task 4: Bootstrap staging and audit the candidate pool

**Files:**
- Create ignored work files under: `artifacts/dataset-curation/`
- Read: `resources/dataset/main/{train,val,test}.jsonl`
- Read: `resources/cases/rejection_checklist.json`
- Read: `resources/cases/user_queries.txt`
- Read only: `test.html`

**Interfaces:**
- Consumes: `bootstrap_staging` from Task 3.
- Produces: four domain shards, mỗi shard có `audit.jsonl` riêng.
- Audit record shape: `{"id":"...","decision":"keep|revise|drop","reason":"..."}`.

- [ ] **Step 1: Capture a clean baseline**

Run: `uv run pytest -q`

Expected: all tests PASS before data curation starts.

- [ ] **Step 2: Bootstrap the current 455 rows into ignored staging**

Invoke `bootstrap_staging(load_release(), load_catalogue(QUERY_CATALOGUE_PATH), Path("artifacts/dataset-curation"))` from a short Python command. Verify the shard row total is exactly 455.

- [ ] **Step 3: Give each author its own candidate subset**

- procedure author: every row whose catalogue domain is `procedure`;
- tuition/rule author: domains `tuition` and `academic-rule`;
- certificate/document author: domains `certificate` and `form`;
- primary agent: `out-of-domain` and real-user inputs.

Each author must write one audit decision for every assigned candidate vào
`artifacts/dataset-curation/<domain>/audit.jsonl` trước khi thêm row mới. Không
agent nào cùng ghi một audit file.

- [ ] **Step 4: Verify audit completeness**

Hợp nhất bốn audit file chỉ để kiểm tra rồi so ID với 455 ID gốc. Expected:
exact equality, no duplicate decision and every `revise`/`drop` has a non-empty
reason.

### Task 5: Curate three in-domain shards in parallel

**Files:**
- Modify ignored: `artifacts/dataset-curation/procedure/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-curation/tuition-academic-rule/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-curation/certificate-form-document/{train,val,test}.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/dataset/main/coverage.json`
- Read: `resources/ontology/ontology.ttl`

**Interfaces:**
- Each author produces three valid JSONL shards plus its audit records.
- Every row must independently pass `validate_dataset(rows, graph, catalogue)`.

- [ ] **Step 1: Dispatch all three authors concurrently**

Use isolated prompts with `fork_turns="none"`. Give each agent only the global constraints, exact query IDs in its domains, allowed paths and required output summary. Explicitly forbid changes outside its shard and audit file.

- [ ] **Step 2: Procedure author fills all 14 procedure families**

Cover all finite procedure IRIs in train; use all four registers for every family in train, validation and test. Prioritize practical questions about instruction, eligibility, deadline, result, submitting/reviewing/deciding actor, required form, download and source. List queries must use natural plural wording rather than synthetic enumeration prompts.

- [ ] **Step 3: Tuition/rule author fills 23 families**

Cover all declared programs, payment methods, class-size rules and numeric cases from `coverage.json`. Questions must state enough conditions to select a unique canonical target. Invalid/outside-range questions are handed to the OOD author instead of receiving empty SPARQL.

- [ ] **Step 4: Certificate/document author fills 13 families**

Cover every declared certificate and form IRI in train plus all numeric certificate cases. Keep certificate type, learner/program context and score explicit when the canonical query needs them. Do not invent a form URL or certificate conversion absent from ontology.

- [ ] **Step 5: Validate every shard split after each completed family batch**

Run `validate_dataset` separately for each non-empty shard split. Expected: valid schema, unique normalized input, catalogue-matching target and non-empty ontology result.

- [ ] **Step 6: Require an author handoff summary**

For each domain report: rows by split/query/register, candidate decisions, uncovered ledger items and quarantined rows. An author may report uncertainty; it may not silently guess.

### Task 6: Curate OOD and real-user regressions while authors run

**Files:**
- Modify ignored: `artifacts/dataset-curation/out-of-domain/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-curation/rejection_checklist.json`
- Modify: `resources/cases/user_queries.txt` only when adding meaningful raw queries found in `test.html`

**Interfaces:**
- Produces all seven rejection classes × four registers × three splits.
- Every OOD row has `query_id == "no-information"` and `target == "không có thông tin"`.

- [ ] **Step 1: Label every meaningful real-user query**

For each input, record whether the current catalogue can answer it completely.
Keep the original input as a held-out regression case; add independently worded
train paraphrases. Put every normalized near-duplicate cluster in one split.

- [ ] **Step 2: Add seven OOD classes by coverage**

Cover greeting/social, unrelated, near-domain-missing, ambiguous,
noisy-out-of-domain, mixed and hard-negative. Every class must have all four
registers in every split. No meaningless character noise is accepted merely to
increase counts.

- [ ] **Step 3: Add hard negatives around every in-domain query family**

Use the entity vocabulary of that family but ask for a relation or missing
condition that the ontology cannot answer. Train has at least one hard negative
for each of the 50 in-domain families; validation/test cover every domain and
all procedure families trọng tâm bằng wording độc lập. Include invalid numeric
ranges for all seven numeric families. Mixed questions with one unsupported
branch reject the entire input.

- [ ] **Step 4: Validate exact marker and checklist integrity**

Check that every checklist ID exists exactly once in the OOD shard, every OOD
row appears in exactly one class, and every class covers all split/register
pairs.

### Task 7: Cross-review all curated shards

**Files:**
- Create ignored: `artifacts/dataset-curation/reviews/procedure.md`
- Create ignored: `artifacts/dataset-curation/reviews/tuition-academic-rule.md`
- Create ignored: `artifacts/dataset-curation/reviews/certificate-form-document.md`
- Create ignored: `artifacts/dataset-curation/reviews/out-of-domain.md`

**Interfaces:**
- Review issue shape: row ID, severity `blocking|minor`, finding, required correction.
- A shard is accepted only when its review has zero unresolved `blocking` issues.

- [ ] **Step 1: Rotate reviewers**

- procedure author reviews tuition/academic-rule;
- tuition/rule author reviews certificate/form/document and OOD;
- certificate/document author reviews procedure.

- [ ] **Step 2: Review semantic correctness row by row**

Compare input meaning, slot values and target. Execute SPARQL but do not treat
non-empty execution as proof that the input means the same thing.

- [ ] **Step 3: Review Vietnamese and split independence row by row**

Reject mechanical paraphrases, unnatural noisy text, wrong register, ambiguous
in-domain questions and near-duplicate wording across splits.

- [ ] **Step 4: Return blocking findings to the original author**

Use follow-up tasks on the same author agent. Reviewer rechecks every corrected
ID and marks it resolved; the primary agent does not waive semantic findings to
make coverage pass.

- [ ] **Step 5: Run the coverage report over the combined staging rows**

Expected: all families, finite slots, numeric cases, priority registers and OOD
cells complete. Any gap returns to the responsible author, not to an automatic
generator.

### Task 8: Assemble and validate the official release

**Files:**
- Replace: `resources/dataset/main/train.jsonl`
- Replace: `resources/dataset/main/val.jsonl`
- Replace: `resources/dataset/main/test.jsonl`
- Replace: `resources/cases/rejection_checklist.json`
- Modify: `tests/research/test_dataset_content.py`

**Interfaces:**
- Consumes only accepted staging rows and remapped checklist from Task 7.
- Produces official release with global `question-NNNNNN` IDs.

- [ ] **Step 1: Assemble into an ignored candidate release directory**

Write first to `artifacts/dataset-curation/release/`, never directly over the
tracked release. Run `validate_release(..., require_complete_catalogue=True)`,
`assess_coverage`, `require_complete_coverage` and checklist integrity there.

- [ ] **Step 2: Run leakage and executable-query validation**

Expected: no exact normalized cross-split duplicates, no same-family near
duplicates above the contract threshold, every in-domain target parses and
returns at least one ontology row, and every finite slot appears in train.

- [ ] **Step 3: Replace the tracked release only after candidate validation**

Copy the three verified JSONL files and remapped checklist. This is a mechanical
release assembly; do not manually edit IDs after copying.

- [ ] **Step 4: Replace stale fixed-count acceptance assertions**

Remove assertions tied to `455`, `24/51` and OOD ratio `0.20–0.35`. Assert the
coverage contract, seven OOD classes, all real-user decisions and `complete ==
True` instead.

- [ ] **Step 5: Run official data tests**

Run: `uv run pytest tests/research/test_dataset.py tests/research/test_dataset_content.py tests/research/test_coverage.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the official data**

```bash
git add resources/dataset/main/train.jsonl resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl resources/cases/rejection_checklist.json resources/cases/user_queries.txt tests/research/test_dataset_content.py
git commit -m "Build the official ontology dataset"
```

### Task 9: Regenerate reports and synchronize public documentation

**Files:**
- Replace: `resources/dataset/main/manifest.json`
- Replace: `reports/dataset.json`
- Replace: `reports/figures/dataset-splits.svg`
- Replace: `reports/figures/registers.svg`
- Replace: `reports/figures/query-features.svg`
- Modify: `README.md`
- Modify: `docs/DATASET.md`
- Modify: `tests/research/test_documentation_status.py`
- Modify: `tests/research/test_reporting.py`

**Interfaces:**
- Public documents describe the final dataset, not staging, agent roles or development stages.
- Every number and checksum comes from generated report/manifest files.

- [ ] **Step 1: Regenerate report, figures and manifest from the final files**

Run: `uv run generate_reports`

Expected: report marks training readiness and coverage complete; manifest
counts/checksums match the new release and `coverage.json`.

- [ ] **Step 2: Update documentation tests before prose**

Require README/DATASET to state the actual record counts, all 51 families,
four registers, seven OOD classes and frozen-test rule. Remove candidate-state
assertions and any wording presenting 455 rows as current production data.

- [ ] **Step 3: Rewrite public dataset sections for an outside reader**

Explain the input/target shape, domain distribution, split purpose, OOD
boundary, source authority and quality gates. Link generated visualizations.
Do not expose `keep/revise/drop`, staging paths, agent assignments or internal
curation rounds.

- [ ] **Step 4: Run the complete verification suite**

Run: `uv run pytest -q`

Run: `uv run validate_sparql_dataset`

Run: `git diff --check`

Expected: all tests PASS; official validation exits 0; no whitespace errors.

- [ ] **Step 5: Inspect final repository scope**

Run: `git status --short --branch`

Expected: only intended tracked dataset/code/docs/report changes plus the
pre-existing user-owned dirty files listed in Global Constraints. No checkpoint,
model, log, cache or staging resource is staged.

- [ ] **Step 6: Commit public reports and documentation**

```bash
git add README.md docs/DATASET.md resources/dataset/main/manifest.json reports/dataset.json reports/figures/dataset-splits.svg reports/figures/registers.svg reports/figures/query-features.svg tests/research/test_documentation_status.py tests/research/test_reporting.py
git commit -m "Document the official dataset"
```

## Deferred follow-up

Fine-tuning chẩn đoán là kế hoạch riêng sau khi Task 9 qua toàn bộ cổng. Lần
fine-tuning đó dùng train/validation để tìm thiếu hụt theo query/register/OOD;
test được đóng băng và chỉ dùng cho benchmark nghiệm thu sau khi dataset ổn
định. Việc tách kế hoạch ngăn GPU training kéo công việc dataset sang sửa model,
script benchmark hoặc web ngoài phạm vi.
