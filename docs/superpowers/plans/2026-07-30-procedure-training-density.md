# Procedure Training Density Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bổ sung đúng 670 câu train được biên soạn thủ công để tăng mật độ 142 target quy trình, giữ nguyên validation/test, rồi fine-tune và nghiệm thu T5Gemma2 đúng một lần.

**Architecture:** Không thêm module hoặc pipeline mới. Công việc chỉ sửa `train.jsonl` theo bốn lô semantic độc lập, dùng validator hiện có để xác minh SPARQL và leakage, sau đó cập nhật contract, manifest, báo cáo và tài liệu trước một lần chạy GPU cuối cùng.

**Tech Stack:** JSON Lines, RDFLib/SPARQL, Python 3.12, pytest, Hugging Face Transformers, PyTorch, T5Gemma2, Fedora Linux, CUDA/BF16 trên RTX 4050 6 GB.

## Global Constraints

- Giữ nguyên từng byte của `resources/dataset/main/val.jsonl` và `resources/dataset/main/test.jsonl`.
- Chỉ thêm vào `resources/dataset/main/train.jsonl`; không sửa hoặc xóa sample hiện có.
- Thêm đúng 670 câu: 202 `neutral`, 202 `noisy`, 134 `formal`, 132 `colloquial`.
- Mọi target quy trình đạt ít nhất 10 câu; 22 target hướng dẫn đạt ít nhất 14; target hướng dẫn đăng ký học phần đạt 20.
- Target canonical của lỗi `noisy` đạt 18 câu, `neutral` đạt 16, `formal` hoặc `colloquial` đạt 14.
- Mỗi target từng lỗi phải nhận ít nhất ba câu mới thuộc chính register đã lỗi; các câu còn lại phải giữ đa dạng register.
- Không sao chép, bỏ dấu hoặc paraphrase sát validation/test.
- Không dùng template rồi chỉ thay tên quy trình.
- Không đổi ontology, catalogue, preprocessing, tokenizer, model, hyperparameter, benchmark hoặc code runtime.
- Không thêm script mới. Chỉ dùng validator, test và reporting hiện có cùng kiểm tra read-only ngắn trong terminal.
- Không chạy GPU trước khi dataset, manifest, reports, docs và toàn bộ static gate đã xanh.
- Chỉ fine-tune T5Gemma2 đúng một lần; không tuning, seed khác hoặc train lại sau khi xem test.
- Không stage hoặc commit các file người dùng đang thay đổi: `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py`, `test_preprocess.py`.
- Không thêm `Co-authored-by` vào commit.

## File Map

- Modify: `resources/dataset/main/train.jsonl` — 670 câu train mới.
- Preserve byte-for-byte: `resources/dataset/main/val.jsonl`, `resources/dataset/main/test.jsonl`.
- Modify: `tests/research/test_dataset_content.py` — contract mật độ mới và checksum khóa validation/test.
- Regenerate: `resources/dataset/main/manifest.json` — checksum và số liệu release mới.
- Regenerate: `reports/dataset.json`, `reports/figures/*.svg` — thống kê công khai.
- Modify: `reports/procedure-dataset.json` — thống kê riêng 142 target quy trình.
- Modify: `README.md`, `docs/DATASET.md`, `docs/EVALUATION.md`, `docs/TRAINING.md`, `resources/dataset/main/README.md`, `reports/README.md` — trạng thái release mới, không kể lịch sử phát triển.
- Create ignored: `artifacts/procedure-density/curation-ledger.json` — quota và bằng chứng vận hành, không phải tài liệu công khai.
- Create ignored: `artifacts/procedure-density/t5gemma2/` — checkpoint, prediction và metric của đúng một lần chạy.

---

### Task 1: Khóa evaluation và lập quota deterministic

**Files:**
- Read: `resources/dataset/main/train.jsonl`
- Read and hash only: `resources/dataset/main/val.jsonl`
- Read and hash only: `resources/dataset/main/test.jsonl`
- Create ignored: `artifacts/procedure-density/curation-ledger.json`

**Interfaces:**
- Consumes: release 2.888 câu và 19 ID lỗi quy trình đã nghiệm thu.
- Produces: ledger chứa quota theo target và phân bổ register toàn vòng; tổng `remaining` phải bằng 670.

- [ ] **Step 1: Xác nhận worktree và snapshot evaluation**

Run:

```bash
git status --short
sha256sum resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl
```

Expected:

```text
063495561b0025b681d96b9b1fc569208a81cd919dfeeb505c1b10ad1da82669  resources/dataset/main/val.jsonl
7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305  resources/dataset/main/test.jsonl
```

- [ ] **Step 2: Khóa đúng 19 test ID dùng để đặt quota**

Use exactly:

```text
question-001728 question-001760 question-001761 question-001767
question-001782 question-001784 question-005030 question-005033
question-005036 question-005039 question-005040 question-005045
question-005046 question-005048 question-005049 question-005059
question-005060 question-005063 question-005097
```

For each ID, read the canonical `target` and `register` from frozen
`test.jsonl`. Do not copy its `input` into the ledger.

- [ ] **Step 3: Tính quota**

Generate the ignored ledger with this one-off mechanical command. It does not
create or modify project code:

```python
import json
from collections import Counter
from pathlib import Path

dataset = Path("resources/dataset/main")
train = [json.loads(line) for line in (dataset / "train.jsonl").read_text().splitlines()]
test = {
    row["id"]: row
    for row in (
        json.loads(line)
        for line in (dataset / "test.jsonl").read_text().splitlines()
    )
}
procedure = [row for row in train if row["query_id"].startswith("procedure-")]
counts = Counter(row["target"] for row in procedure)
instruction = {
    row["target"] for row in procedure
    if row["query_id"] == "procedure-instruction"
}
course = next(
    target for target in instruction
    if ":CourseRegistrationProcedure" in target
)
error_ids = """question-001728 question-001760 question-001761 question-001767
question-001782 question-001784 question-005030 question-005033
question-005036 question-005039 question-005040 question-005045
question-005046 question-005048 question-005049 question-005059
question-005060 question-005063 question-005097""".split()
error_register = {test[row_id]["target"]: test[row_id]["register"] for row_id in error_ids}
query_for_target = {row["target"]: row["query_id"] for row in procedure}
for target in instruction:
    query_for_target[target] = "procedure-instruction"

targets = []
for target, current in sorted(counts.items()):
    required = 10
    if target in instruction:
        required = max(required, 14)
    if target == course:
        required = max(required, 20)
    if target in error_register:
        required = max(required, {
            "noisy": 18,
            "neutral": 16,
            "formal": 14,
            "colloquial": 14,
        }[error_register[target]])
    targets.append({
        "query_id": query_for_target[target],
        "target": target,
        "current": current,
        "required": required,
        "remaining": required - current,
        "error_register": error_register.get(target),
    })

ledger = {
    "frozen_val_sha256": "063495561b0025b681d96b9b1fc569208a81cd919dfeeb505c1b10ad1da82669",
    "frozen_test_sha256": "7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305",
    "new_registers": {"formal": 134, "neutral": 202, "colloquial": 132, "noisy": 202},
    "targets": targets,
}
assert len(targets) == 142
assert len(error_register) == 19
assert sum(row["remaining"] for row in targets) == 670
assert Counter(row["required"] for row in targets) == Counter({10: 103, 14: 23, 16: 5, 18: 10, 20: 1})
output = Path("artifacts/procedure-density/curation-ledger.json")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n")
```

The ledger must report:

```text
targets = 142
priority_error_targets = 19
new_rows = 670
required histogram = {10: 103, 14: 23, 16: 5, 18: 10, 20: 1}
```

Assign the 670 rows globally as:

```text
neutral = 202
noisy = 202
formal = 134
colloquial = 132
```

- [ ] **Step 4: Kiểm tra ledger trước biên soạn**

Confirm the four semantic batches:

```text
Batch A — list/deadline/decision/eligibility = 199
Batch B — form/office routing                 = 179
Batch C — instruction/source                  = 202
Batch D — result                              = 90
Total                                         = 670
```

If any number differs, stop. Do not change the quota rules to force the total.
This task creates no tracked change and therefore has no commit.

---

### Task 2: Biên soạn Batch A — list, deadline, authority và eligibility

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/ontology/ontology.ttl`
- Read: `artifacts/procedure-density/curation-ledger.json`

**Interfaces:**
- Consumes: quota ledger Task 1.
- Produces: 199 dòng `question-005107` đến `question-005305`.

- [ ] **Step 1: Viết 199 câu độc lập**

Add exactly:

```text
procedure-list                9
procedure-deadline           46
procedure-decision-authority 32
procedure-eligibility       112
```

Within this batch use exactly 60 `neutral`, 60 `noisy`, 40 `formal` and 39
`colloquial`. Questions must distinguish the named procedure and requested
attribute; each `noisy` question must remain human-readable.

- [ ] **Step 2: Review every input-target pair**

For each row, compare the wording with the actual ontology answer and with
neighbor targets of the same procedure. Reject rows that could naturally mean
two different attributes. Do not consult the text of the frozen test questions.

- [ ] **Step 3: Verify the batch**

Run:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

rows = [json.loads(line) for line in Path("resources/dataset/main/train.jsonl").read_text().splitlines()]
batch = [row for row in rows if 5107 <= int(row["id"].split("-")[-1]) <= 5305]
assert [int(row["id"].split("-")[-1]) for row in batch] == list(range(5107, 5306))
assert Counter(row["query_id"] for row in batch) == Counter({
    "procedure-list": 9,
    "procedure-deadline": 46,
    "procedure-decision-authority": 32,
    "procedure-eligibility": 112,
})
assert Counter(row["register"] for row in batch) == Counter({
    "formal": 40, "neutral": 60, "colloquial": 39, "noisy": 60,
})
assert len(rows) == 2278
assert sum(row["query_id"].startswith("procedure-") for row in rows) == 1161
PY
uv run validate_sparql_dataset >/dev/null
git diff --check -- resources/dataset/main/train.jsonl
```

Expected: all assertions and both commands exit 0.

- [ ] **Step 4: Commit Batch A only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen procedure conditions and deadlines"
```

---

### Task 3: Biên soạn Batch B — biểu mẫu và tuyến xử lý

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/ontology/ontology.ttl`
- Read: `artifacts/procedure-density/curation-ledger.json`

**Interfaces:**
- Consumes: Batch A đã qua validator.
- Produces: 179 dòng `question-005306` đến `question-005484`.

- [ ] **Step 1: Viết 179 câu độc lập**

Add exactly:

```text
procedure-form-download      42
procedure-required-form      66
procedure-review-office      15
procedure-submission-office  56
```

Within this batch use exactly 54 `neutral`, 54 `noisy`, 36 `formal` and 35
`colloquial`. Contrast at least these meanings: tên biểu mẫu, link tải biểu
mẫu, nơi nhận hồ sơ và nơi thẩm định/xử lý.

- [ ] **Step 2: Review every input-target pair**

Ensure words such as `đơn`, `mẫu`, `link`, `nộp`, `nhận`, `xử lý` express the
actual requested output rather than acting as a single-keyword template.

- [ ] **Step 3: Verify the batch**

Run:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

rows = [json.loads(line) for line in Path("resources/dataset/main/train.jsonl").read_text().splitlines()]
batch = [row for row in rows if 5306 <= int(row["id"].split("-")[-1]) <= 5484]
assert [int(row["id"].split("-")[-1]) for row in batch] == list(range(5306, 5485))
assert Counter(row["query_id"] for row in batch) == Counter({
    "procedure-form-download": 42,
    "procedure-required-form": 66,
    "procedure-review-office": 15,
    "procedure-submission-office": 56,
})
assert Counter(row["register"] for row in batch) == Counter({
    "formal": 36, "neutral": 54, "colloquial": 35, "noisy": 54,
})
assert len(rows) == 2457
assert sum(row["query_id"].startswith("procedure-") for row in rows) == 1340
PY
uv run validate_sparql_dataset >/dev/null
git diff --check -- resources/dataset/main/train.jsonl
```

Expected: all assertions and both commands exit 0.

- [ ] **Step 4: Commit Batch B only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen procedure forms and routing"
```

---

### Task 4: Biên soạn Batch C — hướng dẫn và nguồn chính thức

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/ontology/ontology.ttl`
- Read: `artifacts/procedure-density/curation-ledger.json`

**Interfaces:**
- Consumes: Batch B đã qua validator.
- Produces: 202 dòng `question-005485` đến `question-005686`.

- [ ] **Step 1: Viết 202 câu độc lập**

Add exactly:

```text
procedure-instruction  98
procedure-source      104
```

Within this batch use exactly 61 `neutral`, 61 `noisy`, 40 `formal` and 40
`colloquial`. All 98 guidance rows use `procedure-instruction`; do not label
them as `procedure-overview`. The batch must distinguish “làm như thế nào”
from “quy định nằm trong văn bản/điều khoản nào”.

- [ ] **Step 2: Review core procedure language**

Give extra scrutiny to course registration, forced withdrawal transfer,
tuition payment, temporary leave, credit recognition and graduation. Ensure
abbreviations already supported by preprocessing are used naturally rather
than appended mechanically.

- [ ] **Step 3: Verify the batch**

Run:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

rows = [json.loads(line) for line in Path("resources/dataset/main/train.jsonl").read_text().splitlines()]
batch = [row for row in rows if 5485 <= int(row["id"].split("-")[-1]) <= 5686]
assert [int(row["id"].split("-")[-1]) for row in batch] == list(range(5485, 5687))
assert Counter(row["query_id"] for row in batch) == Counter({
    "procedure-instruction": 98,
    "procedure-source": 104,
})
assert Counter(row["register"] for row in batch) == Counter({
    "formal": 40, "neutral": 61, "colloquial": 40, "noisy": 61,
})
assert len(rows) == 2659
assert sum(row["query_id"].startswith("procedure-") for row in rows) == 1542
PY
uv run validate_sparql_dataset >/dev/null
git diff --check -- resources/dataset/main/train.jsonl
```

Expected: all assertions and both commands exit 0.

- [ ] **Step 4: Commit Batch C only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen procedure guidance and sources"
```

---

### Task 5: Biên soạn Batch D — kết quả của quy trình

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Read: `resources/dataset/main/catalogue.jsonl`
- Read: `resources/ontology/ontology.ttl`
- Read: `artifacts/procedure-density/curation-ledger.json`

**Interfaces:**
- Consumes: Batch C đã qua validator.
- Produces: 90 dòng `question-005687` đến `question-005776` và release train đủ quota.

- [ ] **Step 1: Viết 90 câu độc lập**

All rows use `procedure-result`. Use exactly 27 `neutral`, 27 `noisy`, 18
`formal` and 18 `colloquial`. Contrast result with instruction and eligibility,
especially for retake, credit recognition, withdrawal, transfer to
work-study education and graduation projects.

- [ ] **Step 2: Review every input-target pair**

Reject a row if it asks what the student must do but the target returns only
the result, or if it asks whether the student is eligible but the target
returns what happens afterward.

- [ ] **Step 3: Verify final curation totals**

Run:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path

rows = [json.loads(line) for line in Path("resources/dataset/main/train.jsonl").read_text().splitlines()]
batch = [row for row in rows if 5687 <= int(row["id"].split("-")[-1]) <= 5776]
added = [row for row in rows if 5107 <= int(row["id"].split("-")[-1]) <= 5776]
ledger = json.loads(Path("artifacts/procedure-density/curation-ledger.json").read_text())
counts = Counter(row["target"] for row in rows if row["query_id"].startswith("procedure-"))
assert [int(row["id"].split("-")[-1]) for row in batch] == list(range(5687, 5777))
assert Counter(row["query_id"] for row in batch) == Counter({"procedure-result": 90})
assert Counter(row["register"] for row in batch) == Counter({
    "formal": 18, "neutral": 27, "colloquial": 18, "noisy": 27,
})
assert Counter(row["register"] for row in added) == Counter({
    "formal": 134, "neutral": 202, "colloquial": 132, "noisy": 202,
})
assert len(rows) == 2749
assert sum(row["query_id"].startswith("procedure-") for row in rows) == 1632
assert all(counts[item["target"]] == item["required"] for item in ledger["targets"])
for item in ledger["targets"]:
    if item["error_register"] is not None:
        assert sum(
            row["target"] == item["target"]
            and row["register"] == item["error_register"]
            for row in added
        ) >= 3
PY
uv run validate_sparql_dataset >/dev/null
git diff --check -- resources/dataset/main/train.jsonl
```

Expected: both exit 0.

- [ ] **Step 4: Commit Batch D only**

```bash
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen procedure result questions"
```

---

### Task 6: Khóa contract và cập nhật release công khai

**Files:**
- Modify: `tests/research/test_dataset_content.py`
- Modify generated: `resources/dataset/main/manifest.json`
- Modify generated: `reports/dataset.json`
- Modify generated: `reports/figures/dataset-splits.svg`
- Modify generated: `reports/figures/registers.svg`
- Modify generated if changed: `reports/figures/query-features.svg`
- Modify: `reports/procedure-dataset.json`
- Modify: `README.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/TRAINING.md`
- Modify: `resources/dataset/main/README.md`
- Modify: `reports/README.md`

**Interfaces:**
- Consumes: release train 2.749 câu, frozen val 402 và frozen test 407.
- Produces: release 3.558 câu có checksum, báo cáo và tài liệu nhất quán.

- [ ] **Step 1: Write the release-contract assertions**

In `tests/research/test_dataset_content.py`:

```python
FROZEN_VAL_SHA256 = "063495561b0025b681d96b9b1fc569208a81cd919dfeeb505c1b10ad1da82669"
FROZEN_TEST_SHA256 = "7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305"
```

Update `test_procedure_first_target_coverage` to require:

```python
assert len(train_counts) == 142
assert min(train_counts.values()) >= 10
assert all(train_counts[target] >= 14 for target in instruction_targets)
assert train_counts[course_target] >= 20
assert Counter(train_counts.values()) == Counter({10: 103, 14: 23, 16: 5, 18: 10, 20: 1})
```

Update the release matrix to:

```python
assert {split: len(rows) for split, rows in release.items()} == {
    "train": 2_749,
    "val": 402,
    "test": 407,
}
assert hashlib.sha256(
    Path("resources/dataset/main/val.jsonl").read_bytes()
).hexdigest() == FROZEN_VAL_SHA256
assert hashlib.sha256(
    Path("resources/dataset/main/test.jsonl").read_bytes()
).hexdigest() == FROZEN_TEST_SHA256
```

- [ ] **Step 2: Run the focused contract**

Run:

```bash
uv run pytest -q tests/research/test_dataset_content.py -k 'procedure_first or final_release_matrix'
```

Expected: PASS.

- [ ] **Step 3: Regenerate canonical manifest and public reports**

Run:

```bash
uv run generate_reports >/dev/null
```

Expected final release summary:

```text
records = 3558
train/val/test = 2749/402/407
procedure domain = 2044
registers = formal 882, neutral 929, colloquial 851, noisy 896
```

- [ ] **Step 4: Update the procedure-specific report**

Set `reports/procedure-dataset.json` to measured values:

```text
train procedure-* rows = 1632
val procedure-* rows = 180
test procedure-* rows = 185
train target histogram = {10: 103, 14: 23, 16: 5, 18: 10, 20: 1}
all 142 train targets retain all four registers
val/test SHA-256 remain unchanged
```

Use the measured train SHA-256 produced by `generate_reports`; do not type a
predicted hash.

- [ ] **Step 5: Update public documentation**

Replace counts and coverage statements in the listed docs. Describe the
current dataset shape and evaluation protocol only; do not mention “vòng”,
“phiên bản”, 19 historical errors or development chronology. State that the
new locked dataset has no official model result until Task 7 completes. Keep
the exact phrase `chưa có benchmark chính thức` contiguous so the public-doc
contract is unambiguous.

- [ ] **Step 6: Run the complete static gate**

Run:

```bash
uv run validate_sparql_dataset >/dev/null
uv run pytest -q
git diff --check
```

Expected: validator exits 0, all tests pass, and `git diff --check` exits 0.
If any tool fails, identify the direct dataset/docs inconsistency only. Do not
refactor or repair unrelated scripts.

- [ ] **Step 7: Commit the locked release**

```bash
git add README.md docs/DATASET.md docs/EVALUATION.md docs/TRAINING.md \
  resources/dataset/main/README.md resources/dataset/main/manifest.json \
  reports/README.md reports/dataset.json reports/procedure-dataset.json \
  reports/figures tests/research/test_dataset_content.py
git commit -m "Lock the expanded procedure training dataset"
```

---

### Task 7: Fine-tune và nghiệm thu T5Gemma2 đúng một lần

**Files:**
- Create ignored: `artifacts/procedure-density/t5gemma2/`
- Read only: locked dataset, manifest and model cache.

**Interfaces:**
- Consumes: Task 6 static gate hoàn toàn xanh.
- Produces: một best checkpoint, test predictions và verdict đạt/không đạt.

- [ ] **Step 1: Preflight không thay code**

Verify:

```text
artifacts/procedure-density/t5gemma2 does not exist
CUDA is available
BF16 is supported
GPU compute capability is at least 8.0
google/t5gemma-2-270m-270m exists in the local Hugging Face cache
train/val/test SHA-256 exactly match manifest.json
```

If any check fails, stop before training.

- [ ] **Step 2: Chạy đúng một lần**

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True uv run train_sparql \
  --model t5gemma2 \
  --output-dir artifacts/procedure-density \
  --epochs 20 \
  --seed 42 \
  --save-model \
  --benchmark-after-training \
  --local-files-only
```

Do not change parameters, retry, resume a failed partial run, or start another
seed without explicit user approval.

- [ ] **Step 3: Evaluate the locked acceptance contract**

Read the generated metrics and compute:

```text
System Answer Exact over all 407 test rows >= 90%
Answer Exact over 185 procedure-* rows >= 95%
formal/neutral/colloquial/noisy procedure accuracy each >= 90%
seven core user queries = 100%
false rejection for CourseRegistration instruction = 0
OOD safe rejection over 90 OOD rows >= 94%
```

- [ ] **Step 4: Report once and stop**

Report runtime, best epoch, validation metric, test metrics, VRAM, verdict and
every remaining `procedure-*` error. Do not modify dataset, docs, code or
hyperparameters after reading test predictions. Do not train again, benchmark
another model or test the web application.

## Explicitly Deferred

- BARTpho and ViT5 benchmark.
- CTranslate2 conversion and deployment.
- Web application and UX testing.
- Ontology or catalogue changes.
- Any third dataset expansion driven by the newly observed test result.
