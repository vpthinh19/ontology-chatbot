# Official SPARQL Query Catalogue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production query catalogue that covers the canonical ontology inventory with user-facing semantic query families while preventing the model from emitting opaque storage-record IRIs.

**Architecture:** Extend the catalogue record with compact class/path coverage selectors, keep answer-scope classification separate from inventory generation, and validate the one-way chain from supported inventory entries to executable SPARQL. The current 455-row release remains a candidate pool and is validated in candidate mode until it is curated against the new catalogue.

**Tech Stack:** Python 3.11+, RDFLib, pytest, JSON Lines, Turtle, existing `ontchatbot.runtime.sparql` safety/execution contract.

## Global Constraints

- Canonical graph: `resources/ontology/ontology.ttl`.
- Catalogue: `resources/dataset/main/catalogue.jsonl`.
- The model may emit finite IRIs for user-facing semantic anchors, never opaque `CertificateConversionRule`, `TuitionRate`, `PaymentFeeRule`, or band-record IRIs.
- Object properties are traversal edges; projected results must be labels, literals, or numeric aggregates.
- `no-information` remains exactly `không có thông tin`.
- Do not curate dataset questions, fine-tune, benchmark, convert models, or modify web runtime in this plan.
- Preserve unrelated user-owned worktree changes and never add AI attribution to commits.

---

## File Structure

- Create `src/ontchatbot/research/answer_scope.py`: canonical classification of source nodes, opaque record nodes, and user-facing semantic anchors.
- Modify `src/ontchatbot/research/inventory.py`: use answer-scope classification and exclude internal record labels deterministically.
- Modify `src/ontchatbot/research/catalogue.py`: parse typed coverage selectors in each catalogue record.
- Create `src/ontchatbot/research/catalogue_validation.py`: inventory-to-catalogue coverage and executable-template audit.
- Modify `resources/ontology/answer_inventory.json`: regenerated output only.
- Modify `resources/dataset/main/catalogue.jsonl`: official semantic query families.
- Modify `src/ontchatbot/research/dataset.py`: distinguish candidate validation from strict official-release coverage.
- Modify focused tests under `tests/research/` and `tests/ontology/`.
- Modify `docs/ONTOLOGY.md`, `docs/DATASET.md`, and the readiness design status after verification.

---

### Task 1: Classify Answer Scope and Remove Internal Labels

**Files:**
- Create: `src/ontchatbot/research/answer_scope.py`
- Modify: `src/ontchatbot/research/inventory.py`
- Modify: `resources/ontology/answer_inventory.json`
- Test: `tests/research/test_inventory.py`

**Interfaces:**
- Produces: `SOURCE_CLASS_NAMES: frozenset[str]`, `OPAQUE_RECORD_CLASS_NAMES: frozenset[str]`, `rdf_type_names(graph: Graph, node: URIRef) -> frozenset[str]`, `is_opaque_record(graph: Graph, node: URIRef) -> bool`.
- Consumes: canonical RDF types from `ontology.ttl`.

- [ ] **Step 1: Write failing inventory-scope tests**

```python
def test_opaque_record_labels_are_not_supported(answer_inventory) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}
    assert entries["StandardEnglishCertificateTableRule03IELTS-rdfs-label"]["status"] == "excluded"
    assert entries["Cohort65InformationTechnologyAccreditedRate-rdfs-label"]["status"] == "excluded"
    assert entries["TemporaryAcademicLeaveProcedure-rdfs-label"]["status"] == "supported"


def test_business_values_inside_opaque_records_remain_supported(answer_inventory) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}
    assert entries["StandardEnglishCertificateTableRule03IELTS-criterionText"]["status"] == "supported"
    assert entries["Cohort65InformationTechnologyAccreditedRate-amount"]["status"] == "supported"
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `uv run pytest tests/research/test_inventory.py -q`

Expected: FAIL because all named-individual labels are currently marked supported.

- [ ] **Step 3: Add the answer-scope classification**

Define opaque record classes exactly as:

```python
OPAQUE_RECORD_CLASS_NAMES = frozenset({
    "CertificateConversionRule",
    "TuitionRate",
    "PaymentFeeRule",
    "AcademicPerformanceBand",
    "GraduationClassificationBand",
    "StudyYearBand",
    "DoctoralTuitionDurationRule",
})
```

Keep `ClassSizeRule` user-addressable because its descriptive IRIs represent
official class categories rather than generated table-row identities. Move the
existing source-type names into `answer_scope.py` and make `inventory.py` import
the shared classification.

When inventory generation encounters `rdfs:label` on an opaque record, append
an `excluded` entry with reason:

```text
Nhãn của bản ghi kỹ thuật nội bộ; truy vấn bằng điều kiện nghiệp vụ thay vì IRI của bản ghi.
```

All other literal and traversed properties remain supported.

- [ ] **Step 4: Regenerate and verify the inventory**

Run: `uv run python -m ontchatbot.research.inventory`

Run: `uv run pytest tests/research/test_inventory.py -q`

Expected: PASS; regenerated manifest equals `build_answer_inventory(graph)`.

- [ ] **Step 5: Commit the answer-scope boundary**

```bash
git add src/ontchatbot/research/answer_scope.py src/ontchatbot/research/inventory.py resources/ontology/answer_inventory.json tests/research/test_inventory.py
git commit -m "Define ontology answer scope"
```

---

### Task 2: Extend the Typed Catalogue Contract with Coverage Selectors

**Files:**
- Modify: `src/ontchatbot/research/catalogue.py`
- Test: `tests/research/test_catalogue.py`

**Interfaces:**
- Produces: `CoverageSelector(anchor_classes: tuple[str, ...], paths: tuple[tuple[str, ...], ...], anchors: tuple[str, ...] = ())`.
- Produces: `QuerySpec.coverage: tuple[CoverageSelector, ...]`.
- Existing `load_catalogue()` and `match_target()` remain the public loading/matching API.

- [ ] **Step 1: Add coverage to test fixtures and write malformed-selector tests**

Use this exact coverage object in the procedure fixture:

```python
"coverage": [{
    "anchor_classes": ["AcademicProcedure"],
    "paths": [["instructionProvision", "officialText"]],
    "anchors": ["CourseRegistrationProcedure", "CourseRetakeProcedure"],
}]
```

Use `"coverage": []` only for `no-information`. Assert rejection for empty
`anchor_classes`, empty `paths`, duplicate values, unsupported fields, malformed
local names, and non-empty coverage on the rejection marker.

- [ ] **Step 2: Run the catalogue tests and verify failure**

Run: `uv run pytest tests/research/test_catalogue.py -q`

Expected: FAIL because catalogue records currently require exactly four fields.

- [ ] **Step 3: Implement the minimal typed parser**

Change required fields to:

```python
_REQUIRED_FIELDS = {"query_id", "domain", "target_template", "slots", "coverage"}
```

Parse only the selector shape approved in the design:

```python
@dataclass(frozen=True)
class CoverageSelector:
    anchor_classes: tuple[str, ...]
    paths: tuple[tuple[str, ...], ...]
    anchors: tuple[str, ...] = ()
```

Local names must match `[A-Za-z][A-Za-z0-9]*`; path components additionally
allow the exact token `rdfs:label`. Reject duplicates rather than silently
normalizing them.

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest tests/research/test_catalogue.py tests/research/test_dataset.py tests/research/test_benchmark.py -q`

Expected: PASS after adding coverage fields to in-test catalogue fixtures.

- [ ] **Step 5: Commit the contract**

```bash
git add src/ontchatbot/research/catalogue.py tests/research/test_catalogue.py tests/research/test_dataset.py tests/research/test_benchmark.py
git commit -m "Add catalogue coverage selectors"
```

---

### Task 3: Validate Inventory Coverage and Semantic IRI Slots

**Files:**
- Create: `src/ontchatbot/research/catalogue_validation.py`
- Create: `tests/research/test_catalogue_validation.py`

**Interfaces:**
- Produces: `CatalogueValidationError(ValueError)`.
- Produces: `validate_catalogue(graph: Graph, inventory: Mapping[str, object], catalogue: Mapping[str, QuerySpec]) -> dict[str, object]`.
- The returned report has `supported_entries`, `covered_entries`, `uncovered_entries`, `overlapping_entries`, `families`, and `domains`.

- [ ] **Step 1: Write failing unit tests for coverage matching**

Construct a two-entry inventory for `TemporaryAcademicLeaveProcedure` with the
paths `instructionProvision/officialText` and `submittedTo/rdfs:label`. Assert:

```python
report = validate_catalogue(graph, inventory, catalogue)
assert report["supported_entries"] == 2
assert report["covered_entries"] == 2
assert report["uncovered_entries"] == []
```

Add failure tests for:

- a supported entry matched by no selector;
- a selector matching no supported entry;
- an anchor listed in a selector but not belonging to an `anchor_classes` type;
- an opaque record IRI in a finite model slot;
- an IRI slot value absent from the graph;
- a non-rejection template with empty coverage.

- [ ] **Step 2: Run the new tests and verify import failure**

Run: `uv run pytest tests/research/test_catalogue_validation.py -q`

Expected: FAIL because `catalogue_validation` does not exist.

- [ ] **Step 3: Implement exact selector matching**

For each supported inventory entry, match a selector only when:

```python
tuple(entry["path"]) in selector.paths
and rdf_type_names(graph, ACADEMIC[entry["anchor"]]) & set(selector.anchor_classes)
and (not selector.anchors or entry["anchor"] in selector.anchors)
```

Validate selector classes, anchors, and paths against the graph before building
the report. Excluded inventory entries do not require catalogue coverage.

- [ ] **Step 4: Validate finite IRI slots**

Every `:LocalName` must exist in the graph. Reject it if its RDF types intersect
`OPAQUE_RECORD_CLASS_NAMES`. Number slots remain dynamic and are not expanded by
the coverage validator.

- [ ] **Step 5: Run focused coverage tests**

Run: `uv run pytest tests/research/test_catalogue_validation.py tests/research/test_catalogue.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the validator**

```bash
git add src/ontchatbot/research/catalogue_validation.py tests/research/test_catalogue_validation.py
git commit -m "Validate ontology catalogue coverage"
```

---

### Task 4: Replace the Candidate Catalogue with Semantic Query Families

**Files:**
- Modify: `resources/dataset/main/catalogue.jsonl`
- Modify: `tests/ontology/test_sparql_smoke.py`
- Modify: `tests/research/test_dataset_content.py`
- Test: `tests/research/test_catalogue_validation.py`

**Interfaces:**
- Consumes: the coverage-selector contract and `validate_catalogue()`.
- Produces: a committed catalogue for the complete supported inventory.

- [ ] **Step 1: Add the canonical-catalogue acceptance test**

```python
def test_canonical_catalogue_covers_supported_inventory(ontology_graph) -> None:
    inventory = json.loads(ANSWER_INVENTORY_PATH.read_text(encoding="utf-8"))
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    report = validate_catalogue(ontology_graph, inventory, catalogue)
    assert report["supported_entries"] == report["covered_entries"]
    assert report["uncovered_entries"] == []
```

Also assert no catalogue slot contains any individual typed as an opaque record.

- [ ] **Step 2: Run the acceptance test and verify failure**

Run: `uv run pytest tests/research/test_catalogue_validation.py::test_canonical_catalogue_covers_supported_inventory -q`

Expected: FAIL because the candidate catalogue has no coverage declarations and
does not cover the inventory.

- [ ] **Step 3: Curate the procedure, policy, form, and document families**

Keep separate query IDs for direct user intentions:

```text
procedure-list
procedure-instruction
procedure-eligibility
procedure-deadline
procedure-result
procedure-source
procedure-submission-office
procedure-review-office
procedure-decision-authority
procedure-required-form
procedure-form-download
policy-list
policy-content
form-list
form-number
form-download
form-source
form-catalogue-page
official-document-list
official-document-metadata
```

Procedure/policy/form IRI slots enumerate only actual semantic individuals that
have the queried path. All templates project `?answer` or explicitly named
literal columns. Keep every target on one canonical line.

- [ ] **Step 4: Curate tuition and payment families**

Use conditions to find record nodes:

```text
tuition-program-cohort-rate
tuition-category-rate
tuition-level-rate
tuition-rate-details
tuition-source
doctoral-tuition-duration
payment-method-list
payment-instruction
payment-method-source
payment-bank-list
payment-fee
payment-warning
```

The primary tuition query uses program + cohort and orders by the largest
applicable `minimumCohortNumber`. It never contains a `TuitionRate` IRI slot.
Payment fees use a `PaymentMethod` slot, never a `PaymentFeeRule` slot.

- [ ] **Step 5: Curate academic-rule and semantic-list families**

Use these query IDs:

```text
academic-performance-band
academic-performance-criteria
study-year-band
study-year-criteria
graduation-classification-band
graduation-classification-criteria
class-size-rule
class-size-source
program-list
program-discipline
program-source
discipline-group-list
discipline-group-source
course-category-list
education-level-list
learner-category-list
learner-category-source
entry-qualification-list
academic-actor-list
bank-list
billing-unit-list
```

The three band lookup queries use numeric slots and min/max filters. The
class-size query may use a finite `ClassSizeRule` slot because those descriptive
IRIs are user-facing semantic anchors, not opaque table-row identifiers.

- [ ] **Step 6: Curate certificate families**

Use semantic certificate/program/competency-level slots only:

```text
certificate-list
certificate-official-name
certificate-source
certificate-conversion-level
certificate-conversion-criteria
certificate-required-level
certificate-course-exemption
certificate-output-standard
computer-certificate-grade
competency-level-list
competency-level-source
course-exemption-list
course-exemption-source
```

Conversion templates find `?rule a :CertificateConversionRule` from the
certificate and any numeric/context slots. No query contains a fixed conversion
rule IRI. Use `ORDER BY DESC(?minimum) LIMIT 1` for score-to-level selection.

- [ ] **Step 7: Add explicit execution tests for dynamic branches**

Extend SPARQL smoke tests with exact assertions for:

- information-technology tuition with cohorts 65, 66, and 67;
- a tuition category with no cohort override;
- academic score exactly on a min/max boundary;
- study credits on a year boundary;
- IELTS score-to-level conversion;
- certificate criteria for a non-English certificate;
- IC3 score conversion at minimum and maximum boundaries;
- doctoral duration for bachelor and master entry qualifications;
- class-size table returning only literal columns.

Run: `uv run pytest tests/ontology/test_sparql_smoke.py tests/research/test_catalogue_validation.py -q`

Expected: PASS with full supported-inventory coverage and executable dynamic
queries.

- [ ] **Step 8: Commit the official catalogue**

```bash
git add resources/dataset/main/catalogue.jsonl tests/ontology/test_sparql_smoke.py tests/research/test_catalogue_validation.py tests/research/test_dataset_content.py
git commit -m "Build official ontology query catalogue"
```

---

### Task 5: Preserve the Candidate Dataset Boundary

**Files:**
- Modify: `src/ontchatbot/research/dataset.py`
- Modify: `tests/research/test_dataset.py`
- Modify: `tests/research/test_dataset_content.py`
- Modify: `src/ontchatbot/research/reporting.py`
- Modify: `tests/research/test_reporting.py`

**Interfaces:**
- Modify: `validate_release(..., require_complete_catalogue: bool = True) -> dict[str, Any]`.
- Candidate reporting calls it with `require_complete_catalogue=False`.
- Training readiness continues to call the default strict mode.

- [ ] **Step 1: Write the candidate/official boundary tests**

```python
def test_candidate_mode_allows_unrepresented_catalogue_families(graph) -> None:
    report = validate_release(splits, graph, catalogue, require_complete_catalogue=False)
    assert report["catalogue_coverage_required"] is False


def test_official_mode_rejects_unrepresented_catalogue_families(graph) -> None:
    with pytest.raises(DatasetError, match="query IDs missing from splits"):
        validate_release(splits, graph, catalogue, require_complete_catalogue=True)
```

Candidate mode must still validate every row's query ID, target template, SPARQL
safety, execution, leakage, and the slot values that the candidate actually
uses. It only skips the assertion that every official family/value is already
represented in all splits.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `uv run pytest tests/research/test_dataset.py tests/research/test_reporting.py -q`

Expected: FAIL because the validation flag does not exist.

- [ ] **Step 3: Implement the explicit validation mode**

Guard only these release-level requirements with `require_complete_catalogue`:

- every query ID occurs in all splits;
- minimum rows/registers for every catalogue query ID;
- every finite slot value occurs in train.

Do not weaken per-row schema, target, SPARQL, ontology execution, duplicate, or
cross-split leakage checks. Add `catalogue_coverage_required` to the report.

- [ ] **Step 4: Point candidate status/reporting tests at relaxed mode**

The committed 455 rows remain candidate. Replace tests that call them
“official release” with candidate terminology and validate them with
`require_complete_catalogue=False`. Training-readiness tests retain strict mode.

- [ ] **Step 5: Run dataset and reporting tests**

Run: `uv run pytest tests/research/test_dataset.py tests/research/test_dataset_content.py tests/research/test_reporting.py tests/research/test_training.py -q`

Expected: PASS; candidate rows remain valid without being misreported as full
catalogue coverage.

- [ ] **Step 6: Commit the boundary**

```bash
git add src/ontchatbot/research/dataset.py src/ontchatbot/research/reporting.py tests/research/test_dataset.py tests/research/test_dataset_content.py tests/research/test_reporting.py tests/research/test_training.py
git commit -m "Separate candidate and official dataset validation"
```

---

### Task 6: Synchronize Documentation and Run the Full Gate

**Files:**
- Modify: `docs/ONTOLOGY.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/superpowers/specs/2026-07-29-ontology-dataset-readiness-design.md`
- Test: `tests/research/test_documentation_status.py`

**Interfaces:**
- Public status must say ontology + inventory + catalogue are canonical.
- Public status must still say the 455 questions are candidate and the official dataset is pending.

- [ ] **Step 1: Update documentation-status assertions first**

Require documentation to contain the concepts `query catalogue`, `canonical`,
`candidate`, and the direction `ontology → inventory → catalogue → dataset`.
Reject claims that full fine-tuning, benchmark, or production web validation is
complete.

- [ ] **Step 2: Run documentation tests and verify failure**

Run: `uv run pytest tests/research/test_documentation_status.py -q`

Expected: FAIL because catalogue status is still pending.

- [ ] **Step 3: Update the three documents**

Explain in plain Vietnamese:

- model-facing IRIs represent things users can name;
- storage rows are selected by query conditions;
- catalogue coverage is complete and machine-checked;
- dataset question curation remains the next gate.

Do not publish development-stage names, obsolete architecture, model scores, or
fine-tuning claims.

- [ ] **Step 4: Run all verification gates**

Run: `uv run pytest -q`

Run: `uv run python -m ontchatbot.research.inventory`

Run: `git diff --exit-code -- resources/ontology/answer_inventory.json`

Run: `git diff --check`

Expected: all tests pass; inventory regeneration has no diff; no whitespace
errors.

- [ ] **Step 5: Inspect repository scope and commit documentation**

Run: `git status --short`

Confirm only the known user-owned changes remain outside the implementation
commits. Then commit:

```bash
git add docs/ONTOLOGY.md docs/DATASET.md docs/superpowers/specs/2026-07-29-ontology-dataset-readiness-design.md tests/research/test_documentation_status.py
git commit -m "Document canonical query catalogue"
```

- [ ] **Step 6: Report the gate in user-facing terms**

Report only:

- how many supported inventory entries and query families were validated;
- which categories of questions are now queryable;
- confirmation that opaque record IRIs are absent from model slots;
- full test result;
- explicit next step: curate the official dataset from the new catalogue.
