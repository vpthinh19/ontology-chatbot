# Balanced Dataset Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bổ sung đúng 896 câu train để phục hồi các lỗi đã đo, khóa một regression suite gồm 308 cách hỏi quy trình, rồi fine-tune và benchmark BARTpho, ViT5, T5Gemma2 bằng cùng giao thức PEFT LoRA.

**Architecture:** Giữ nguyên ontology, catalogue, preprocessing, schema SPARQL và runtime. Bốn khối dữ liệu ngữ nghĩa được triển khai thành năm batch độc lập vì khối ngôn ngữ quy trình được chia đôi; mỗi batch có ID và quota cố định, validator hiện có kiểm tra sau từng batch. Một thay đổi nhỏ trong research CLI cho phép đánh giá checkpoint trên regression suite tùy chọn mà không tạo script tạm.

**Tech Stack:** JSON Lines, RDFLib/SPARQL, Python 3.12, pytest, Hugging Face Transformers, PEFT, PyTorch, BARTpho, ViT5, T5Gemma2, Fedora Linux, CUDA/BF16 trên RTX 4050 6 GB.

## Global Constraints

- Làm việc trên nhánh `refactor/direct-sparql`; không merge khi chưa đạt toàn bộ cổng nghiệm thu.
- Giữ nguyên từng byte của `resources/dataset/main/val.jsonl` và `resources/dataset/main/test.jsonl`.
- Chỉ thêm vào `resources/dataset/main/train.jsonl`; không sửa hoặc xóa sample hiện có.
- Thêm đúng 896 câu với ID `question-005777` đến `question-006672`.
- Register mới phải đúng: noisy 314, neutral 224, colloquial 224, formal 134.
- Không sao chép, bỏ dấu hoặc paraphrase sát validation/test/regression suite.
- Trong 896 câu train, không dùng template rồi chỉ thay tên thực thể; mọi câu
  phải được review semantic thủ công. Ma trận template cố định chỉ được dùng cho
  regression suite 308 câu và không đi vào train.
- Mọi target SPARQL phải khớp catalogue, thực thi được và trả dữ liệu không rỗng.
- Mọi OOD mới dùng `query_id=no-information`, target `không có thông tin` và phải được phân loại trong `resources/cases/rejection_checklist.json`.
- Không thay ontology, catalogue, preprocessing, tokenizer, model, hyperparameter hoặc code runtime.
- Không thêm generator cho dataset. Script chỉ được đếm, validate và báo cáo.
- Không chạy GPU trước khi regression suite, dataset, manifest, reports, docs và toàn bộ static gate đều xanh.
- Chỉ fine-tune mỗi model từ checkpoint pretrained gốc đúng một lần; không resume checkpoint cũ, tuning, seed khác hoặc train lại sau khi xem test.
- Giữ cấu hình: PEFT LoRA rank 32/alpha 64/dropout 0, physical/effective batch 8, gradient accumulation 1, 20 epochs, seed 42, learning rate `1e-4`, cosine scheduler, `warmup_steps=0.1`, eval mỗi 2 epochs, dynamic padding, BF16/TF32 theo phần cứng, không gradient checkpointing, greedy decoding, không `torch.compile`.
- Không stage hoặc commit các file người dùng đang thay đổi: `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py`, `test_preprocess.py`.
- Không thêm `Co-authored-by` vào commit.

## File Map

- Create: `resources/cases/procedure_language.jsonl` — 308 regression cases, không thuộc train/val/test.
- Modify: `src/ontchatbot/settings.py` — đường dẫn regression suite.
- Modify: `src/ontchatbot/research/evaluate_transformers.py` — nhận `--benchmark` tùy chọn.
- Modify: `tests/research/test_benchmark.py` — contract regression suite và parser CLI.
- Modify append-only: `resources/dataset/main/train.jsonl` — 896 câu mới.
- Modify: `resources/cases/rejection_checklist.json` — phân loại 220 OOD mới.
- Modify: `tests/research/test_dataset_content.py` — contract năm batch và release mới.
- Regenerate: `resources/dataset/main/manifest.json`, `reports/dataset.json`, `reports/figures/*.svg`.
- Modify: `reports/procedure-dataset.json` — thống kê target quy trình mới.
- Modify: `tests/research/test_reporting.py` — số lượng release mới.
- Modify: `README.md`, `docs/DATASET.md`, `docs/EVALUATION.md`, `docs/TRAINING.md`, `resources/dataset/main/README.md`, `reports/README.md` — trạng thái dataset hiện hành, không kể lịch sử phát triển.
- Create ignored: `artifacts/balanced-recovery/` — ledger, baseline regression, checkpoint và metrics.

---

### Task 1: Khóa regression suite và công cụ đánh giá

**Files:**
- Create: `resources/cases/procedure_language.jsonl`
- Modify: `src/ontchatbot/settings.py`
- Modify: `src/ontchatbot/research/evaluate_transformers.py`
- Modify: `tests/research/test_benchmark.py`
- Create ignored: `artifacts/balanced-recovery/curation-ledger.json`

**Interfaces:**
- Consumes: 22 IRI trong slot `procedure-instruction`, checkpoint chẩn đoán theo giao thức cũ tại `artifacts/procedure-density/t5gemma2/model`.
- Produces: `PROCEDURE_LANGUAGE_CASES_PATH`, CLI `evaluate_sparql_model --benchmark PATH`, suite 220 positive + 88 negative và ledger quota năm batch.

- [x] **Step 1: Viết test contract trước khi tạo suite**

Add to `tests/research/test_benchmark.py`:

```python
from collections import Counter
from pathlib import Path

from ontchatbot.research.benchmark import load_benchmark
from ontchatbot.research.dataset import load_release
from ontchatbot.research.evaluate_transformers import _parse_args
from ontchatbot.runtime.text import normalize_model_input
from ontchatbot.settings import PROCEDURE_LANGUAGE_CASES_PATH


def test_procedure_language_suite_is_disjoint_and_complete() -> None:
    rows = load_benchmark(PROCEDURE_LANGUAGE_CASES_PATH)
    release = load_release()
    release_questions = {
        normalize_model_input(row["input"]).casefold()
        for split in ("train", "val", "test")
        for row in release[split]
    }
    positive = [row for row in rows if row["query_id"] == "procedure-instruction"]
    negative = [row for row in rows if row["query_id"] == "no-information"]
    positive_targets = Counter(row["target"] for row in positive)

    assert len(rows) == 308
    assert len(positive) == 220
    assert len(negative) == 88
    assert len({row["id"] for row in rows}) == 308
    assert not release_questions & {
        normalize_model_input(row["input"]).casefold() for row in rows
    }
    assert len(positive_targets) == 22
    assert set(positive_targets.values()) == {10}
    assert all(row["target"] == "không có thông tin" for row in negative)


def test_transformers_evaluator_accepts_custom_benchmark(tmp_path: Path) -> None:
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    benchmark = tmp_path / "cases.jsonl"
    benchmark.write_text("", encoding="utf-8")

    args = _parse_args([
        "--model", "t5gemma2",
        "--model-dir", str(model_dir),
        "--suite", "benchmark",
        "--benchmark", str(benchmark),
    ])

    assert args.benchmark == benchmark
```

- [x] **Step 2: Chạy test để xác nhận thất bại đúng lý do**

```bash
uv run pytest tests/research/test_benchmark.py \
  -k 'procedure_language or custom_benchmark' -q
```

Expected: FAIL vì chưa có `PROCEDURE_LANGUAGE_CASES_PATH` và `_parse_args` chưa nhận argv/`--benchmark`.

- [x] **Step 3: Thêm giao diện đánh giá tối thiểu**

In `src/ontchatbot/settings.py`, add:

```python
PROCEDURE_LANGUAGE_CASES_PATH = RESOURCES / "cases" / "procedure_language.jsonl"
```

In `src/ontchatbot/research/evaluate_transformers.py`, import `TEST_DATASET_PATH`, load `load_benchmark(args.benchmark)`, then change the parser to:

```python
def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODEL_SPECS), required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--suite", choices=("validation", "benchmark", "both"), default="both")
    parser.add_argument("--benchmark", type=Path, default=TEST_DATASET_PATH)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
```

Keep the existing model-directory and positive-batch-size checks. This is research-only plumbing; do not alter generation or model loading.

- [x] **Step 4: Tạo 308 regression cases bằng `apply_patch`**

Use exactly these 22 IRI/anchor pairs:

| IRI | Anchor tiếng Việt |
|---|---|
| `ArticulationStudyProcedure` | học liên thông |
| `ClassAbsenceRequestProcedure` | xin phép nghỉ học |
| `CourseExemptionAndBonusProcedure` | miễn học, miễn thi và cộng điểm thưởng |
| `CourseRegistrationProcedure` | đăng ký học phần |
| `CourseRetakeProcedure` | đăng ký học lại |
| `CreditRecognitionProcedure` | công nhận kết quả học tập và chuyển đổi tín chỉ |
| `DismissalTransferRequestProcedure` | xin chuyển chương trình sau khi bị buộc thôi học |
| `EarlyGraduationReviewProcedure` | đề nghị xét tốt nghiệp sớm |
| `ExamPostponementProcedure` | xin hoãn thi |
| `ExtraClassOpeningRequestProcedure` | đề nghị mở thêm lớp học phần |
| `GradeImprovementProcedure` | đăng ký học cải thiện |
| `GraduationProjectRegistrationProcedure` | đăng ký đồ án hoặc khóa luận tốt nghiệp |
| `GraduationReviewProcedure` | xét và công nhận tốt nghiệp |
| `MajorChangeProcedure` | chuyển ngành |
| `SecondProgramRegistrationProcedure` | học cùng lúc hai chương trình |
| `SickLeaveProcedure` | xin nghỉ ốm |
| `StudentExchangeProcedure` | tham gia chương trình trao đổi sinh viên |
| `StudyResumptionProcedure` | xin học trở lại |
| `StudyWithdrawalProcedure` | xin thôi học |
| `TemporaryAcademicLeaveProcedure` | xin nghỉ học tạm thời |
| `TuitionPaymentProcedure` | đóng học phí |
| `UniversityTransferProcedure` | chuyển trường |

For every anchor create ten positive patterns:

```text
X như nào
X như thế nào
X ra sao
X sao
làm sao để X
làm thế nào để X
muốn X thì làm sao
muốn X thì làm thế nào
cần làm gì để X
hướng dẫn X
```

Positive target:

```text
SELECT ?answer WHERE { :IRI :instructionProvision ?part . ?part :officialText ?answer . }
```

For every anchor create four negative patterns:

```text
vì sao phải X
X để làm gì
X là gì
lợi ích của X là gì
```

Negative rows use `query_id=no-information` and target `không có thông tin`. IDs are `procedure-language-0001` through `procedure-language-0308`. Assign registers exactly as follows:

```text
positive colloquial: X như nào; X sao; làm sao để X; muốn X thì làm sao
positive neutral:    X như thế nào; X ra sao; làm thế nào để X;
                     muốn X thì làm thế nào; cần làm gì để X
positive formal:     hướng dẫn X
negative neutral:    vì sao phải X; X là gì
negative colloquial: X để làm gì
negative formal:     lợi ích của X là gì
```

Hai pattern của `CourseRegistrationProcedure` trùng sau preprocessing với test
đã khóa, nên suite dùng `đăng ký học phần như thế nào vậy` và `đăng ký học phần
sao vậy`. Không thay hoặc sao chép hai câu test gốc.

- [x] **Step 5: Chạy test và validate suite**

```bash
uv run pytest tests/research/test_benchmark.py -q
uv run benchmark_sparql \
  --benchmark resources/cases/procedure_language.jsonl \
  --output artifacts/balanced-recovery/reference-procedure-language.json
git diff --check -- resources/cases/procedure_language.jsonl \
  src/ontchatbot/settings.py src/ontchatbot/research/evaluate_transformers.py \
  tests/research/test_benchmark.py
```

Expected: tests pass; reference report has 308/308 System Answer Exact.

- [x] **Step 6: Ghi baseline chẩn đoán từ checkpoint cũ**

```bash
uv run evaluate_sparql_model \
  --model t5gemma2 \
  --model-dir artifacts/procedure-density/t5gemma2/model \
  --suite benchmark \
  --benchmark resources/cases/procedure_language.jsonl \
  --batch-size 8 \
  --output-dir artifacts/balanced-recovery/baseline-procedure-language
```

Verify positive 211/220 and negative safe rejection 11/88. If the reconstructed suite differs, record the actual baseline in the ignored ledger; do not modify the suite to force previous numbers.

- [x] **Step 7: Tạo ignored ledger**

Create `artifacts/balanced-recovery/curation-ledger.json` with:

```json
{
  "frozen_val_sha256": "063495561b0025b681d96b9b1fc569208a81cd919dfeeb505c1b10ad1da82669",
  "frozen_test_sha256": "7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305",
  "new_rows": 896,
  "registers": {"noisy": 314, "neutral": 224, "colloquial": 224, "formal": 134},
  "batches": {"A1": 176, "A2": 176, "B": 144, "C": 220, "D": 180}
}
```

- [x] **Step 8: Commit regression tooling only**

```bash
git add resources/cases/procedure_language.jsonl src/ontchatbot/settings.py \
  src/ontchatbot/research/evaluate_transformers.py tests/research/test_benchmark.py
git commit -m "Add procedure language regression suite"
```

Do not add `artifacts/`.

---

### Task 2: Biên soạn Block A1 — 11 quy trình đầu

**Files:**
- Modify append-only: `resources/dataset/main/train.jsonl`
- Read: `resources/cases/procedure_language.jsonl`
- Read: `resources/ontology/ontology.ttl`

**Interfaces:**
- Consumes: regression suite Task 1.
- Produces: 176 rows `question-005777` through `question-005952`.

- [x] **Step 1: Biên soạn 16 câu cho mỗi quy trình**

Use the first 11 IRI/anchor pairs in Task 1, ending at `GradeImprovementProcedure`. For four procedures use register mix `noisy=5, neutral=4, colloquial=4, formal=3`; for seven procedures use `noisy=6, neutral=4, colloquial=4, formal=2`.

Block total:

```text
records=176 noisy=62 neutral=44 colloquial=44 formal=26
```

All rows use `query_id=procedure-instruction` and the canonical instruction target. Include the language families in the spec, but do not copy a regression input verbatim.

- [x] **Step 2: Review every input-target pair**

For every row verify: procedure is unambiguous; the question asks how to perform it; abbreviations survive `normalize_model_input`; no wording asks eligibility, deadline, form, office, result or source.

- [x] **Step 3: Verify Block A1**

Run a read-only count over ID range 5777–5952 and assert exact ID sequence, 176 rows, 11 targets ×16 and register quota. Then run:

```bash
uv run validate_sparql_dataset >/dev/null
git diff --check -- resources/dataset/main/train.jsonl
```

- [x] **Step 4: Commit Block A1 only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Expand basic procedure language coverage"
```

---

### Task 3: Biên soạn Block A2 — 11 quy trình còn lại

**Files:**
- Modify append-only: `resources/dataset/main/train.jsonl`
- Read: `resources/cases/procedure_language.jsonl`
- Read: `resources/ontology/ontology.ttl`

**Interfaces:**
- Consumes: Block A1 ending at ID 5952.
- Produces: 176 rows `question-005953` through `question-006128`.

- [x] **Step 1: Biên soạn 16 câu cho mỗi quy trình**

Use the final 11 IRI/anchor pairs in Task 1, beginning at `GraduationProjectRegistrationProcedure`. Four procedures use `noisy=5, neutral=4, colloquial=4, formal=3`; seven use `noisy=6, neutral=4, colloquial=4, formal=2`. Block total is exactly:

```text
records=176 noisy=62 neutral=44 colloquial=44 formal=26
```

- [x] **Step 2: Review semantic và leakage**

For every row verify that the procedure is unambiguous, the question asks how to perform it, abbreviations survive `normalize_model_input`, and the wording does not ask eligibility, deadline, form, office, result or source. Pay special attention to `StudyWithdrawalProcedure`, `TemporaryAcademicLeaveProcedure`, `SickLeaveProcedure` and `ClassAbsenceRequestProcedure`; their everyday wording must not collapse into one another.

- [x] **Step 3: Verify Block A2 and combined Block A**

Assert ID range 5953–6128, 176 rows and quota. Across 5777–6128 assert 352 rows and exactly 16 rows for each of 22 procedure instruction targets. Run validator and `git diff --check`.

- [x] **Step 4: Commit Block A2 only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Complete basic procedure language coverage"
```

---

### Task 4: Biên soạn Block B — thuộc tính quy trình dễ nhầm

**Files:**
- Modify append-only: `resources/dataset/main/train.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/ontology/ontology.ttl`

**Interfaces:**
- Consumes: nine canonical targets in the design spec.
- Produces: 144 rows `question-006129` through `question-006272`.

- [ ] **Step 1: Khóa chín target**

Use exactly these query/IRI pairs, 16 rows each:

```text
procedure-instruction   CourseRegistrationProcedure
procedure-eligibility   ExamPostponementProcedure
procedure-form-download TemporaryAcademicLeaveProcedure
procedure-overview      TuitionPaymentProcedure
procedure-source        UniversityTransferProcedure
procedure-deadline      ExamPostponementProcedure
procedure-instruction   ClassAbsenceRequestProcedure
procedure-overview      TemporaryAcademicLeaveProcedure
procedure-result        UniversityTransferProcedure
```

Five targets use mix `noisy=6, neutral=4, colloquial=4, formal=2`; four targets use `noisy=5, neutral=4, colloquial=4, formal=3`. Block total:

```text
records=144 noisy=50 neutral=36 colloquial=36 formal=22
```

- [ ] **Step 2: Biên soạn contrast packs**

For each target, read all sibling targets of the same procedure. Every new question must contain a semantic cue unique to the intended property. Review pairs side by side, especially deadline versus eligibility, source versus result, overview versus form download.

- [ ] **Step 3: Verify Block B**

Assert exact ID sequence, nine targets ×16, query/IRI pairs and register quota. Run validator and `git diff --check`.

- [ ] **Step 4: Commit Block B only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen procedure intent contrasts"
```

---

### Task 5: Biên soạn Block C — OOD gần miền

**Files:**
- Modify append-only: `resources/dataset/main/train.jsonl`
- Modify: `resources/cases/rejection_checklist.json`
- Read: `resources/cases/procedure_language.jsonl`

**Interfaces:**
- Consumes: 22 procedure anchors and rejection classes hiện có.
- Produces: 220 rows `question-006273` through `question-006492`, all target `không có thông tin`.

- [ ] **Step 1: Biên soạn 10 OOD cho mỗi quy trình**

For every procedure create:

```text
near-domain-missing = 3
ambiguous           = 2
mixed               = 2
hard-negative       = 3
```

For 11 procedures use register mix `noisy=4, neutral=2, colloquial=2, formal=2`; for 11 procedures use `noisy=3, neutral=3, colloquial=3, formal=1`. Block total:

```text
records=220 noisy=77 neutral=55 colloquial=55 formal=33
```

- [ ] **Step 2: Review every negative against ontology**

Confirm the requested fact is absent. Reject any negative answerable by an instruction, eligibility, deadline, office, form, result or source target. Mixed questions combine an answerable request with an unsupported request because product policy rejects the whole compound request.

- [ ] **Step 3: Update rejection checklist**

Append every new ID to exactly one of `near-domain-missing`, `ambiguous`, `mixed`, or `hard-negative` according to allocation 3/2/2/3. Do not alter existing IDs or other classes.

- [ ] **Step 4: Verify Block C**

Assert ID sequence, 220 rows, 22 anchors ×10, marker, query ID, register totals and checklist partition. Run:

```bash
uv run validate_sparql_dataset >/dev/null
uv run pytest tests/research/test_dataset_content.py \
  -k rejection_checklist -q
git diff --check -- resources/dataset/main/train.jsonl \
  resources/cases/rejection_checklist.json
```

- [ ] **Step 5: Commit Block C only**

```bash
git add resources/dataset/main/train.jsonl resources/cases/rejection_checklist.json
git commit -m "Add near-domain procedure rejections"
```

---

### Task 6: Biên soạn Block D — phục hồi ngoài quy trình

**Files:**
- Modify append-only: `resources/dataset/main/train.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/ontology/ontology.ttl`

**Interfaces:**
- Consumes: 16 query family đã đo lỗi.
- Produces: 180 rows `question-006493` through `question-006672`.

- [ ] **Step 1: Phân bổ family quota**

Use exactly:

```text
class-size-rule                14
academic-actor-list            12
doctoral-tuition-details       12
form-download                  12
payment-method-details         12
payment-method-list            11
payment-bank-list              11
payment-fee                    11
payment-warning                11
academic-performance-band      11
academic-program-details       11
certificate-conversion-details 11
class-size-details             11
form-document-details          10
graduation-classification-band 10
official-document-metadata     10
```

The sum is 180. Global register quota:

```text
noisy=63 neutral=45 colloquial=45 formal=27
```

Every family must contain all four registers.

- [ ] **Step 2: Biên soạn theo nguyên nhân lỗi**

Use multi-column wording for targets with several return fields, explicit entity cues for class/form/payment IRIs and diverse decimals for numeric targets. For numeric questions verify the input literal equals every occurrence in target after preprocessing; include one- and two-decimal values.

- [ ] **Step 3: Verify Block D and complete quota**

Assert exact ID range, family counts, registers and total. Across IDs 5777–6672 assert:

```text
records=896 noisy=314 neutral=224 colloquial=224 formal=134
```

Run validator and `git diff --check`.

- [ ] **Step 4: Commit Block D only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen remaining query families"
```

---

### Task 7: Khóa release, reports và tài liệu

**Files:**
- Modify: `tests/research/test_dataset_content.py`
- Modify: `tests/research/test_reporting.py`
- Regenerate: `resources/dataset/main/manifest.json`
- Regenerate: `reports/dataset.json`
- Regenerate: `reports/figures/*.svg`
- Modify: `reports/procedure-dataset.json`
- Modify: `README.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/TRAINING.md`
- Modify: `resources/dataset/main/README.md`
- Modify: `reports/README.md`

**Interfaces:**
- Consumes: completed 3.645-row train and frozen validation/test.
- Produces: a static-green release with manifest provenance before GPU work.

- [ ] **Step 1: Update release contract tests**

Change release sizes to:

```python
assert {split: len(rows) for split, rows in release.items()} == {
    "train": 3_645,
    "val": 402,
    "test": 407,
}
```

Keep frozen SHA constants unchanged. Add this contract test, retaining the existing `Counter` import:

```python
def test_balanced_recovery_batches_match_locked_contract() -> None:
    rows = load_release()["train"]
    numbered = {
        int(row["id"].rsplit("-", 1)[-1]): row
        for row in rows
        if row["id"].startswith("question-")
    }
    new = [numbered[number] for number in range(5777, 6673)]

    assert len(new) == 896
    assert Counter(row["register"] for row in new) == Counter({
        "noisy": 314, "neutral": 224, "colloquial": 224, "formal": 134,
    })

    a1 = [numbered[number] for number in range(5777, 5953)]
    a2 = [numbered[number] for number in range(5953, 6129)]
    for batch in (a1, a2):
        assert len(batch) == 176
        assert {row["query_id"] for row in batch} == {"procedure-instruction"}
        assert Counter(Counter(row["target"] for row in batch).values()) == Counter({16: 11})
        assert Counter(row["register"] for row in batch) == Counter({
            "noisy": 62, "neutral": 44, "colloquial": 44, "formal": 26,
        })

    block_b = [numbered[number] for number in range(6129, 6273)]
    assert Counter(Counter(row["target"] for row in block_b).values()) == Counter({16: 9})
    assert Counter(row["register"] for row in block_b) == Counter({
        "noisy": 50, "neutral": 36, "colloquial": 36, "formal": 22,
    })

    block_c = [numbered[number] for number in range(6273, 6493)]
    assert {row["query_id"] for row in block_c} == {"no-information"}
    assert {row["target"] for row in block_c} == {"không có thông tin"}
    assert Counter(row["register"] for row in block_c) == Counter({
        "noisy": 77, "neutral": 55, "colloquial": 55, "formal": 33,
    })

    block_d = [numbered[number] for number in range(6493, 6673)]
    assert Counter(row["query_id"] for row in block_d) == Counter({
        "class-size-rule": 14,
        "academic-actor-list": 12,
        "doctoral-tuition-details": 12,
        "form-download": 12,
        "payment-method-details": 12,
        "payment-method-list": 11,
        "payment-bank-list": 11,
        "payment-fee": 11,
        "payment-warning": 11,
        "academic-performance-band": 11,
        "academic-program-details": 11,
        "certificate-conversion-details": 11,
        "class-size-details": 11,
        "form-document-details": 10,
        "graduation-classification-band": 10,
        "official-document-metadata": 10,
    })
    assert Counter(row["register"] for row in block_d) == Counter({
        "noisy": 63, "neutral": 45, "colloquial": 45, "formal": 27,
    })
```

Replace the procedure target histogram assertion with:

```python
assert Counter(train_counts.values()) == Counter({
    10: 99, 14: 4, 16: 4, 18: 8, 26: 4,
    30: 17, 34: 2, 46: 2, 48: 1, 52: 1,
})
```

Update the exact train count for `certificate-conversion-details` from 27 to 38. In `test_recovered_training_set_strengthens_measured_weak_families`, update these values and leave all others unchanged:

```text
academic-actor-list=26
academic-program-details=25
class-size-details=25
payment-fee=27
payment-method-details=26
payment-method-list=27
payment-warning=27
```

Change `tests/research/test_reporting.py`:

```python
assert report["dataset"]["records"] == 4454
```

- [ ] **Step 2: Run the new contract tests**

```bash
uv run pytest tests/research/test_dataset_content.py \
  tests/research/test_reporting.py -q
```

Expected: PASS. If a quota fails, fix only the responsible new row; do not relax the contract.

- [ ] **Step 3: Regenerate canonical outputs**

```bash
uv run generate_reports
```

Expected: manifest, `reports/dataset.json` and SVG figures reflect 4.454 rows and 3.645 train rows. Validation/test hashes remain frozen.

- [ ] **Step 4: Update procedure-specific report**

Measure procedure rows by split, target density, register and SHA-256 with a read-only command. Apply those exact measured values to `reports/procedure-dataset.json`. It must still describe 142 canonical procedure targets and contain no development history.

- [ ] **Step 5: Update public documentation**

Replace stale counts and distributions in the listed docs. State training and regression evaluation are pending; do not publish old 2.749-row training metrics as current. Document the 308-case suite as a production acceptance check, not an independent scientific benchmark.

- [ ] **Step 6: Run the complete static gate**

```bash
uv run pytest -q
uv run validate_sparql_dataset >/dev/null
uv run benchmark_sparql \
  --benchmark resources/cases/procedure_language.jsonl >/dev/null
git diff --check
sha256sum resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl
```

Expected: all tests pass; validator exits 0; regression reference validates; hashes match the frozen values.

- [ ] **Step 7: Commit the locked release**

```bash
git add README.md docs/DATASET.md docs/EVALUATION.md docs/TRAINING.md \
  resources/dataset/main/README.md resources/dataset/main/manifest.json \
  reports/README.md reports/dataset.json reports/procedure-dataset.json \
  reports/figures tests/research/test_dataset_content.py \
  tests/research/test_reporting.py
git commit -m "Lock balanced production dataset"
```

---

### Task 8: Fine-tune và benchmark ba model đúng một lần

**Files:**
- Create ignored: `artifacts/model-benchmark/{bartpho,vit5,t5gemma2}/`
- Create ignored: `artifacts/model-benchmark/procedure-language/{bartpho,vit5,t5gemma2}/`
- Read only: locked dataset, regression suite, manifest and local model cache.

**Interfaces:**
- Consumes: Task 7 static gate completely green.
- Produces: three best checkpoints, comparable validation/test/regression predictions and one model-selection report.

- [ ] **Step 1: Preflight không thay code**

Verify:

```text
three model output directories do not exist
CUDA is available
BF16 is supported
GPU compute capability is at least 8.0
all three pinned model revisions exist in the local Hugging Face cache
train/val/test SHA-256 exactly match manifest.json
regression suite has 308 rows and no normalized overlap with train
PEFT smoke train batch dài nhất của dataset cuối chạy được với physical batch 8
```

If any check fails, stop before training.

- [ ] **Step 2: Chạy PEFT LoRA fine-tuning đúng một lần**

Run `train_sparql` once for each of `bartpho`, `vit5`, `t5gemma2`, using
`artifacts/model-benchmark` as the common output root and the exact shared
arguments in `docs/TRAINING.md`. Keep one separate log per model and stop the
sequence if any command exits non-zero.

Do not change parameters, retry, resume a failed partial run or start another seed without explicit user approval. Record actual wall time; do not promise an estimate before the final dataset smoke test.

- [ ] **Step 3: Đánh giá regression suite từ saved artifact**

Only if Step 2 exits 0:

```bash
for model in bartpho vit5 t5gemma2; do
  uv run evaluate_sparql_model \
    --model "$model" \
    --model-dir "artifacts/model-benchmark/$model/model" \
    --suite benchmark \
    --benchmark resources/cases/procedure_language.jsonl \
    --batch-size 8 \
    --output-dir "artifacts/model-benchmark/procedure-language/$model" || break
done
```

- [ ] **Step 4: Compute the locked acceptance contract**

Report every metric below for all three models. Apply all thresholds as one
production gate to the checkpoint selected for deployment; comparison models
may remain below a threshold without invalidating the benchmark.

```text
220 positive regression rows: System Answer Exact = 100%
88 negative regression rows: safe rejection >= 95%
407 current test rows: System Answer Exact >= 90%
185 procedure-* test rows: Answer Exact >= 95%
formal/neutral/colloquial/noisy procedure accuracy each >= 90%
three CourseRegistration instruction test rows = 3/3
90 OOD test rows: safe rejection >= 94%
```

Report the same metrics for each model: runtime, best epoch, validation Answer
Exact, peak VRAM, every remaining procedure error and all regression failures.
Compare only the three locked runs; do not tune one model after seeing results.

- [ ] **Step 5: Report once and stop**

Do not modify dataset, docs, code or hyperparameters after reading predictions.
Do not train again, convert to CTranslate2, test the web app or merge the branch.

## Explicitly Deferred

- Fresh blind scientific holdout.
- CTranslate2 conversion and deployment.
- Web application and UX testing.
- Ontology, catalogue, preprocessing or runtime changes.
- Any further dataset recovery driven by the new test result.
