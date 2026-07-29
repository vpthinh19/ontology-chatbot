# Production Dataset Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not dispatch subagents unless the user explicitly re-authorizes their cost.

**Goal:** Nâng dataset chính thức từ 953 lên tối thiểu 2.000 câu chất lượng cao, giữ một model runtime xử lý cả SPARQL và `không có thông tin`, rồi đồng bộ báo cáo công khai trước khi fine-tuning.

**Architecture:** Giữ 953 câu hiện tại làm lõi đã kiểm định. Rút gọn đúng tám target đã được audit và phê duyệt, bootstrap release vào staging mới, bổ sung thủ công theo sáu miền và lắp lại release sau từng batch để tiến độ được lưu bằng Git. Chỉ chạy validation dữ liệu nhanh theo batch; full suite chạy một lần ở cuối.

**Tech Stack:** Python 3.12, RDFLib, SPARQL 1.1, pytest, Hugging Face tokenizers, JSON Lines, Git, Fedora Linux.

## Global Constraints

- Điểm bắt đầu: branch `refactor/direct-sparql`, release 953 câu tại commit `8694d9f`; các microfix sau đó giữ nguyên số dòng.
- Dataset đích tối thiểu 2.000 câu; chấp nhận 2.000–2.100 khi câu bổ sung có giá trị, không tạo câu rác để đạt số lượng chính xác.
- Ma trận chuẩn ở mốc 2.000 là train 1.400, validation 300, test 300.
- Một model runtime sinh một trong hai dạng output: SPARQL canonical hoặc chính xác `không có thông tin`; không có gate model riêng.
- Dataset phải round-trip an toàn qua tokenizer BARTpho, ViT5 và T5Gemma2; việc benchmark sau này mới quyết định model production.
- Target tối đa 160 token, input tối đa 128 token, không `<unk>` và không bị thay đổi khi encode/decode.
- Không fine-tuning, benchmark, chạy web, sửa inference, deploy hoặc viết tài liệu công khai trong Tasks 1–8.
- Không chạy `uv run pytest -q` sau từng batch; chỉ chạy validation được nêu trong task. Full suite chỉ chạy ở Task 9.
- Không tự mở nhánh sửa lỗi phụ. Nếu lỗi ngoài phạm vi xuất hiện, ghi vào report và dừng task tại checkpoint Git gần nhất.
- Không sinh câu hỏi bằng script hoặc phép tổ hợp template. Mỗi sample mới phải được biên soạn và đọc lại về nghĩa.
- Mỗi record có đúng năm field: `id`, `query_id`, `register`, `input`, `target`; không thêm `origin`, version hoặc metadata quá trình phát triển.
- In-domain chỉ dùng query family có thật trong catalogue; target phải match canonical template và trả ít nhất một dòng ontology.
- OOD luôn có `query_id == "no-information"` và `target == "không có thông tin"`; câu hỗn hợp có một nhánh không hỗ trợ phải bị từ chối toàn bộ.
- Câu noisy phải vẫn có nghĩa đối với người Việt; không dùng chuỗi ký tự vô nghĩa hoặc lỗi lặp token để tăng số lượng.
- Test chỉ được đóng băng sau khi đạt quy mô đích; sau Task 8 không di chuyển, viết lại hoặc dùng test để tuning.
- Không dùng multi-seed, GPU training hoặc model checkpoint trong kế hoạch này.
- Không thêm `Co-authored-by` vào commit.
- Bảo toàn file người dùng: `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py`, `test_preprocess.py`.
- Không merge branch trong kế hoạch này.

## Current and Target Matrix

| Domain | Current train/val/test | Target train/val/test | Add train/val/test | Add total |
| --- | ---: | ---: | ---: | ---: |
| procedure | 178/56/59 | 420/90/90 | 242/34/31 | 307 |
| tuition | 79/24/24 | 175/38/37 | 96/14/13 | 123 |
| academic-rule | 88/22/22 | 140/30/30 | 52/8/8 | 68 |
| certificate | 105/16/16 | 161/35/34 | 56/19/18 | 93 |
| form | 35/10/10 | 84/18/18 | 49/8/8 | 65 |
| out-of-domain | 118/45/46 | 420/89/91 | 302/44/45 | 391 |
| **Total** | **603/173/177** | **1.400/300/300** | **797/127/123** | **1.047** |

OOD target totals:

| Rejection class | Current | Target | Add |
| --- | ---: | ---: | ---: |
| greeting-social | 20 | 50 | 30 |
| unrelated | 20 | 60 | 40 |
| near-domain-missing | 20 | 100 | 80 |
| ambiguous | 25 | 100 | 75 |
| noisy-out-of-domain | 12 | 60 | 48 |
| mixed | 20 | 80 | 60 |
| hard-negative | 92 | 150 | 58 |
| **Total** | **209** | **600** | **391** |

## Quality Matrix for New Questions

Mỗi query family in-domain phải được mở rộng bằng các dạng phù hợp với nghĩa của nó:

1. câu trực tiếp chính quy;
2. câu nói tự nhiên/đời thường;
3. câu có viết tắt hoặc không dấu nhưng vẫn hiểu được;
4. câu tình huống gián tiếp nêu đủ điều kiện chọn target;
5. câu phân biệt với family hoặc quan hệ lân cận.

Không bắt buộc mỗi family có số dòng bằng nhau. Ưu tiên family người dùng thực tế hay hỏi: hướng dẫn, điều kiện, hạn, nơi nộp, biểu mẫu, học phí ngành/khóa, quy đổi chứng chỉ và các hard negative sát miền.

---

### Task 1: Compact the audited model-facing targets

**Files:**
- Modify: `resources/dataset/main/catalogue.jsonl`
- Modify: `resources/dataset/main/{train,val,test}.jsonl`
- Modify: `tests/ontology/test_sparql_smoke.py`
- Modify: `tests/research/test_dataset_content.py`
- Modify: `tests/tools/test_model_tokenizers.py`

**Interfaces:**
- Consumes: the official rows belonging to the eight audited query families below.
- Produces: semantically equivalent queries whose instantiated targets fit the 160-token contract.

The one-time audit approved on 2026-07-29 locked this batch. Besides
`tuition-rate-details`, it contains exactly: `academic-performance-details`,
`class-size-details`, `doctoral-tuition-details`,
`graduation-classification-details`, `language-certificate-level`,
`official-document-metadata`, and `payment-method-details`. Do not open another
target family during this task.

- [x] **Step 1: Add failing semantic and tokenizer regressions**

Require this exact template:

```sparql
SELECT DISTINCT ?document ?answer WHERE { ?rate a :TuitionRate ; :sourceDocument/rdfs:label ?document ; :sourceProvision/:officialText ?answer . }
```

Assert execution returns one row, `document == "Quyết định số 729/QĐ-ĐHNT"`, and `answer` contains the official tuition-table header plus representative undergraduate rates.

- [x] **Step 2: Confirm RED**

Run:

```bash
uv run pytest tests/ontology/test_sparql_smoke.py tests/research/test_dataset_content.py tests/tools/test_model_tokenizers.py -q
```

Expected: failures identify the old 10-column template and the 160-token overflow.

- [x] **Step 3: Apply the minimal canonical migration**

Replace only the catalogue templates and their instantiated targets. Preserve every row's ID, input, query ID, register, order and split.

- [x] **Step 4: Verify GREEN without opening another fix**

Run:

```bash
uv run pytest tests/ontology/test_sparql_smoke.py tests/research/test_catalogue_validation.py tests/research/test_dataset.py tests/research/test_dataset_content.py tests/tools/test_model_tokenizers.py -q
uv run validate_sparql_dataset
git diff --check
```

Expected: semantic, dataset and all-target tokenizer checks pass. The one-time audit batch is closed after this gate.

- [x] **Step 5: Commit**

```bash
git add resources/dataset/main/catalogue.jsonl resources/dataset/main/train.jsonl resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl tests/ontology/test_sparql_smoke.py tests/research/test_dataset_content.py tests/tools/test_model_tokenizers.py
git commit -m "Compact model-facing detail queries"
```

### Task 2: Bootstrap expansion staging and lock the baseline

**Files:**
- Create ignored: `artifacts/dataset-expansion/{procedure,tuition-academic-rule,certificate-form-document,out-of-domain}/{train,val,test}.jsonl`
- Create ignored: `artifacts/dataset-expansion/rejection_checklist.json`
- Create ignored: `artifacts/dataset-expansion/progress.md`

**Interfaces:**
- Consumes: current tracked 953-row official release after Task 1.
- Produces: a byte-equivalent four-shard staging workspace and a physical count ledger.

- [x] **Step 1: Bootstrap from the tracked release**

Run `bootstrap_staging(load_release(), load_catalogue(QUERY_CATALOGUE_PATH), Path("artifacts/dataset-expansion"))` from a short `uv run python -c` command.

- [x] **Step 2: Verify exact equality after assembly**

Run `assemble_staging(Path("artifacts/dataset-expansion"))`, compare all five fields in split order with the tracked release after ignoring mechanically reassigned IDs, and verify the rejection checklist maps the same 209 OOD inputs to the same seven classes.

- [x] **Step 3: Write the starting ledger**

`artifacts/dataset-expansion/progress.md` must record the Current and Target Matrix above, current Git hash, zero additions, and the rule that only checked-off rows may enter assembly.

### Task 3: Expand procedure data in two bounded batches

**Files:**
- Modify ignored: `artifacts/dataset-expansion/procedure/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-expansion/progress.md`
- Replace mechanically after each batch: `resources/dataset/main/{train,val,test}.jsonl`
- Replace mechanically after each batch: `resources/cases/rejection_checklist.json`

**Interfaces:**
- Consumes: 293 accepted procedure rows across 14 families.
- Produces: exactly 600 procedure rows, split 420/90/90.

- [ ] **Step 1: Author batch P1**

Add exactly 154 meaningful procedure rows: 121 train, 17 validation, 16 test. Prioritize instruction, eligibility, deadline, result, submission/review/decision roles, required form/download and real-life indirect wording. Do not create a result row where ontology has no `resultProvision`.

- [ ] **Step 2: Validate and persist P1**

Run split-level `validate_dataset`, subset `validate_release(..., require_complete_catalogue=False)`, and the cross-split near-duplicate check. Assemble all staging, run full release coverage, mechanically replace tracked splits/checklist, then commit only those four tracked data files with message `Expand procedure questions`.

- [ ] **Step 3: Author batch P2**

Add exactly 153 procedure rows: 121 train, 17 validation, 15 test. Fill family/register gaps left by P1; no wording may be a token-swapped copy of P1.

- [ ] **Step 4: Validate and persist P2**

Repeat the P1 data-only gates. Expected final procedure counts: 420/90/90. Commit the same four tracked files with message `Complete procedure coverage expansion`.

### Task 4: Expand tuition and academic-rule data

**Files:**
- Modify ignored: `artifacts/dataset-expansion/tuition-academic-rule/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-expansion/progress.md`
- Replace mechanically: tracked splits and rejection checklist.

**Interfaces:**
- Consumes: 127 tuition and 132 academic-rule rows.
- Produces: tuition 250 rows (175/38/37) and academic-rule 200 rows (140/30/30).

- [ ] **Step 1: Author tuition additions**

Add 123 rows split 96/14/13. Every program/cohort question must name the relevant course category when multiple rates could apply. Full-table questions use `tuition-rate-details`; specific questions use the narrower family.

- [ ] **Step 2: Author academic-rule additions**

Add 68 rows split 52/8/8. Emphasize numeric boundaries, natural scale statements, table-detail requests and hard-to-confuse wording. Invalid numeric gaps remain OOD.

- [ ] **Step 3: Validate, assemble and commit**

Run data-only validation, coverage and leakage gates. Expected combined domain counts match the target matrix. Replace tracked data mechanically and commit with message `Expand tuition and academic rule questions`.

### Task 5: Expand certificate and form data

**Files:**
- Modify ignored: `artifacts/dataset-expansion/certificate-form-document/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-expansion/progress.md`
- Replace mechanically: tracked splits and rejection checklist.

**Interfaces:**
- Consumes: 137 certificate and 55 form rows.
- Produces: certificate 230 rows (161/35/34) and form 120 rows (84/18/18).

- [ ] **Step 1: Add certificate questions**

Add 93 rows split 56/19/18. State certificate type, score and learner/program context whenever the selected family requires them. Full conversion-table requests must use the compact parent-table target; point lookup uses the score/criterion family.

- [ ] **Step 2: Add form questions**

Add 65 rows split 49/8/8. Cover form identification, catalogue listing, download and natural descriptions of use; never invent a URL or form absent from ontology.

- [ ] **Step 3: Validate, assemble and commit**

Run data-only validation, coverage, exact URL execution and leakage gates. Replace tracked data mechanically and commit with message `Expand certificate and form questions`.

### Task 6: Expand OOD batch O1

**Files:**
- Modify ignored: `artifacts/dataset-expansion/out-of-domain/{train,val,test}.jsonl`
- Modify ignored: `artifacts/dataset-expansion/rejection_checklist.json`
- Modify ignored: `artifacts/dataset-expansion/progress.md`
- Replace mechanically: tracked splits and rejection checklist.

**Interfaces:**
- Consumes: 209 accepted OOD rows.
- Produces: first 196 of 391 new OOD rows, split 151/22/23.

- [ ] **Step 1: Author O1 against the class ledger**

Add meaningful rows toward the final class totals, prioritizing ambiguous, near-domain-missing and mixed questions. Keep class membership exact and ask for genuinely missing relations/live data in hard negatives.

- [ ] **Step 2: Validate checklist and language**

Every OOD ID must occur exactly once in the checklist; every checklist ID must resolve to one OOD row. Verify exact marker, natural Vietnamese, register label and no cross-split near duplicate.

- [ ] **Step 3: Assemble and commit**

Replace tracked data mechanically and commit with message `Expand out of domain questions`.

### Task 7: Expand OOD batch O2 and reach the target matrix

**Files:** Same as Task 6.

**Interfaces:**
- Consumes: OOD after O1.
- Produces: remaining 195 rows split 151/22/22 and final OOD count 600.

- [ ] **Step 1: Fill exact OOD class totals**

Reach exactly 50 greeting-social, 60 unrelated, 100 near-domain-missing, 100 ambiguous, 60 noisy-out-of-domain, 80 mixed and 150 hard-negative rows.

- [ ] **Step 2: Validate all six domain targets**

Assemble staging and assert the complete Current and Target Matrix now equals 2.000 rows and 1.400/300/300 splits. Require all 51 families, numeric cases, finite slots, registers, seven rejection classes and all real-user inputs.

- [ ] **Step 3: Commit the completed expanded release**

```bash
git add resources/dataset/main/train.jsonl resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl resources/cases/rejection_checklist.json
git commit -m "Complete the production ontology dataset"
```

### Task 8: Freeze test and perform one semantic acceptance review

**Files:**
- Modify: `tests/research/test_dataset_content.py`
- Read only after freeze: `resources/dataset/main/test.jsonl`

**Interfaces:**
- Consumes: final 2.000-row release.
- Produces: executable assertions for final counts, frozen real-user queries and immutable test checksum.

- [ ] **Step 1: Review only the 1.047 newly added rows**

Check input meaning against target/query family, ambiguity, natural register and split independence. Do not reread the unchanged 953-row core unless a new row conflicts with it.

- [ ] **Step 2: Resolve findings in place**

Replace bad new rows one-for-one so the matrix remains exact. Re-run only the affected shard and combined leakage gates.

- [ ] **Step 3: Freeze test by checksum**

Add a test asserting the final test-file SHA-256 and that all seven `resources/cases/user_queries.txt` inputs occur exactly once in test with their accepted canonical decisions.

- [ ] **Step 4: Commit acceptance tests**

```bash
git add tests/research/test_dataset_content.py resources/dataset/main/train.jsonl resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl resources/cases/rejection_checklist.json
git commit -m "Freeze the production dataset test split"
```

### Task 9: Generate reports, synchronize public documentation and run the single full gate

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
- Consumes: frozen final release.
- Produces: public Vietnamese documentation and the only full-suite result for this plan.

- [ ] **Step 1: Update reporting tests before prose**

Replace every 455/953 candidate assertion with generated final counts, all 51 families, six domains, four registers, seven OOD classes, complete coverage and the frozen-test rule.

- [ ] **Step 2: Generate canonical artifacts**

Run:

```bash
uv run generate_reports
```

Require manifest/report checksums to match the tracked release and `coverage.json`; training readiness and coverage must be complete.

- [ ] **Step 3: Rewrite public dataset sections in Vietnamese**

Describe input/target shapes, split purposes, domain/register/OOD distributions, source authority, quality gates and generated visualizations. Do not expose staging paths, agents, keep/revise/drop decisions or development versions.

- [ ] **Step 4: Run the only full verification pass**

```bash
uv run pytest -q
uv run validate_sparql_dataset
git diff --check
git status --short --branch
```

Expected: all tests pass; validator reports exactly the final matrix with complete coverage; only pre-existing user-owned dirt remains unstaged.

- [ ] **Step 5: Commit public state**

```bash
git add README.md docs/DATASET.md resources/dataset/main/manifest.json reports/dataset.json reports/figures/dataset-splits.svg reports/figures/registers.svg reports/figures/query-features.svg tests/research/test_documentation_status.py tests/research/test_reporting.py
git commit -m "Document the production ontology dataset"
```

## Explicitly Deferred

- Fine-tuning, hyperparameter changes and GPU execution.
- Model benchmark and production-model selection.
- Web application and UX testing.
- CTranslate2 conversion.
- Deployment.
- Any ontology expansion not required to validate a sample in the matrix above.

These activities require separate plans after Task 9 is green.
