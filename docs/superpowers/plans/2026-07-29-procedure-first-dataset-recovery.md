# Procedure-First Dataset Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến quy trình học vụ thành miền được dạy và kiểm chứng chắc chắn nhất của model, với mọi target quy trình có đủ dữ liệu train và xuất hiện độc lập trong validation/test.

**Architecture:** Giữ nguyên ontology, catalogue, model và giao thức huấn luyện. Audit ngữ nghĩa 156 câu quy trình đánh giá hiện có, bổ sung thủ công theo từng target SPARQL, khóa test trước khi dùng GPU, rồi fine-tune T5Gemma2 đúng một lần để nghiệm thu.

**Tech Stack:** JSON Lines, RDFLib/SPARQL 1.1, pytest, Hugging Face Transformers, PyTorch CUDA, Git trên Fedora Linux.

## Global Constraints

- Quy trình học vụ là miền ưu tiên tuyệt đối; positive quy trình trong train phải ít nhất gấp hai lần `no-information`.
- Không sửa ontology, query catalogue, SPARQL schema, preprocessing, tokenizer, model, hyperparameter hoặc backend.
- Không tái chia split, không chuyển câu giữa các split và không đưa cách viết val/test vào train.
- Không dùng script sinh câu hoặc thay từ hàng loạt; mọi câu mới được biên soạn và đọc lại về nghĩa.
- Chỉ chỉnh câu val/test khi câu hỏi, SPARQL và kết quả ontology chứng minh không khớp; giữ nguyên ID và split.
- Không sửa CLI, package, reporting code hoặc test ngoài assertion trực tiếp khóa dataset mới.
- Nếu script phụ lỗi nhưng không chặn dataset, bỏ qua và ghi nhận. Nếu lỗi chặn audit, validation, fine-tuning hoặc benchmark, dừng và báo cáo; không tự sửa.
- Không chạy smoke train, GPU train, benchmark hoặc web test trong Tasks 1–7.
- Chỉ chạy T5Gemma2 một lần ở Task 8; không tuning, seed khác hoặc train lại theo lỗi test.
- Test bổ sung phải được khóa trước Task 8 và không thay đổi sau khi xem prediction.
- Không thêm `Co-authored-by`, không merge branch, và bảo toàn toàn bộ file bẩn hiện có của người dùng.

## File Map

- Modify: `resources/dataset/main/train.jsonl`
- Modify: `resources/dataset/main/val.jsonl`
- Modify: `resources/dataset/main/test.jsonl`
- Modify: `resources/cases/rejection_checklist.json`
- Create ignored: `artifacts/dataset-procedure-recovery/evaluation-audit.json`
- Create: `reports/procedure-dataset.json`
- Modify: `tests/research/test_dataset_content.py`
- Regenerate: `resources/dataset/main/manifest.json`, `reports/dataset.json`, `reports/figures/*.svg`
- Synchronize: `README.md`, `docs/DATASET.md`, `docs/EVALUATION.md`, `resources/dataset/main/README.md`
- Create ignored after the data gate: `artifacts/procedure-recovery/t5gemma2/`

---

### Task 1: Audit ngữ nghĩa 156 câu quy trình trong validation/test

**Files:**
- Create ignored: `artifacts/dataset-procedure-recovery/evaluation-audit.json`
- Modify only when proven necessary: `resources/dataset/main/val.jsonl`
- Modify only when proven necessary: `resources/dataset/main/test.jsonl`

**Interfaces:**
- Consumes: 78 câu `procedure-*` trong validation, 78 câu trong test và ontology canonical.
- Produces: quyết định `keep`, `revise-input` hoặc `revise-target` cho từng ID.

- [ ] **Step 1: Tạo ledger audit đúng schema**

Mỗi bản ghi có `id`, `split`, `status`, `reason`; bản ghi sửa thêm `old_input`, `new_input` hoặc `old_target`, `new_target`. Ledger phải chứa đúng 156 ID duy nhất và chỉ dùng ba trạng thái đã khóa.

- [ ] **Step 2: Audit đủ 78 câu validation**

Với từng câu, so input với literal do `execute_select(load_ontology(), target)` trả. Xem kỹ `question-001440`, `question-001451`, `question-001464`, nhưng không dừng ở các ví dụ này.

- [ ] **Step 3: Audit đủ 78 câu test**

Áp dụng cùng tiêu chí. Xem kỹ `question-001712`, `question-001737`, `question-001753`, `question-001774`, `question-001776`, `question-001787`.

- [ ] **Step 4: Áp dụng duy nhất sửa đổi có bằng chứng**

Giữ nguyên ID, query ID, register, vị trí và split. Nếu câu nhiều ý không được một target catalogue trả đủ, rút input về một ý được hỗ trợ; không mở query family mới.

- [ ] **Step 5: Xác minh và commit**

Run:

```bash
uv run validate_sparql_dataset
git diff --check
git add resources/dataset/main/val.jsonl resources/dataset/main/test.jsonl
git commit -m "Correct procedure evaluation semantics"
```

Expected: validator qua và không leakage. Nếu 156 câu đều `keep`, không tạo commit rỗng.

### Task 2: Làm dày toàn bộ target hướng dẫn quy trình

**Files:**
- Modify: `resources/dataset/main/train.jsonl`

**Interfaces:**
- Consumes: 22 target dùng `instructionProvision`, hiện có tổng 100 câu instruction/overview.
- Produces: thêm đúng 122 positive để có 222 câu; mỗi target có ít nhất 6 câu hướng dẫn trực tiếp và 4 câu tổng quan, riêng đăng ký học phần có 12 câu.

- [ ] **Step 1: Thêm bảy câu đăng ký học phần**

Target là `SELECT ?answer WHERE { :CourseRegistrationProcedure :instructionProvision ?part . ?part :officialText ?answer . }`. Phủ câu ngắn khẩu ngữ, không dấu, `đk hp`, `chọn môn`, đăng ký khối lượng học tập, hướng dẫn trực tiếp và yêu cầu toàn bộ quy định; không sao chép ba câu test người dùng.

- [ ] **Step 2: Thêm 115 câu cho 21 target còn lại**

Mỗi target đạt ít nhất 6 dòng `procedure-instruction`, 4 dòng `procedure-overview` và đủ formal, neutral, colloquial, noisy trên target chung.

- [ ] **Step 3: Rà các cặp dễ nhầm**

Đọc riêng các cặp học lại môn/trở lại học, chuyển ngành/chuyển trường, chương trình thứ hai/liên thông, trao đổi sinh viên/công nhận tín chỉ, hướng dẫn học phí/phương thức thanh toán.

- [ ] **Step 4: Xác minh và commit batch**

```bash
uv run validate_sparql_dataset
git diff --check
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen academic procedure guidance"
```

### Task 3: Làm dày các target điều khoản nội dung

**Files:**
- Modify: `resources/dataset/main/train.jsonl`

**Interfaces:**
- Consumes: deadline, eligibility, result và source targets hiện tại.
- Produces: thêm đúng 250 positive; mọi target đạt ít nhất 6, target từng sai benchmark đạt ít nhất 8.

- [ ] **Step 1: Thêm 33 câu deadline** — phân biệt thời hạn với điều kiện; câu nhiều mốc chỉ hợp lệ khi literal trả đủ các mốc.
- [ ] **Step 2: Thêm 73 câu eligibility** — phủ “được không”, “ai được”, “cần đạt gì”, tình huống gián tiếp và noisy đủ nghĩa.
- [ ] **Step 3: Thêm 54 câu result** — hỏi hệ quả sau giải quyết, không hỏi các bước thực hiện.
- [ ] **Step 4: Thêm 90 câu source** — hỏi văn bản gốc, điều khoản, căn cứ hoặc nội dung chính thức; không dùng từ “đầy đủ” nếu target hướng dẫn phù hợp hơn.
- [ ] **Step 5: Xác minh và commit batch**

```bash
uv run validate_sparql_dataset
git diff --check
git add resources/dataset/main/train.jsonl
git commit -m "Strengthen procedure provision questions"
```

### Task 4: Làm dày đường nối thực thể và ranh giới từ chối

**Files:**
- Modify: `resources/dataset/main/train.jsonl`
- Modify: `resources/cases/rejection_checklist.json`

**Interfaces:**
- Consumes: authority, form download, required form, review office, submission office.
- Produces: thêm đúng 149 positive và 8 hard negative; train có 962 positive quy trình và 428 `no-information`.

- [ ] **Step 1: Thêm đúng 149 positive**

```text
procedure-decision-authority  24
procedure-form-download       26
procedure-required-form       52
procedure-review-office        2
procedure-submission-office   45
```

Phân biệt “mẫu nào”/label, “tải ở đâu”/URL, “nộp ở đâu”/nơi tiếp nhận, “ai xét”/đơn vị thẩm định và “ai quyết định”/thẩm quyền.

- [ ] **Step 2: Thêm đúng tám hard negative**

Dùng ID `question-003600`–`question-003607`. Phủ: lý do phải đăng ký học phần, môn dễ qua, giảng viên nên chọn, dự đoán duyệt, trạng thái hồ sơ, thời gian xử lý thực tế, cách nộp “ít lỗi nhất”, và hỗ trợ chi phí ngoài quy định. Thêm mỗi ID đúng một lần vào nhóm `hard-negative`.

- [ ] **Step 3: Xác minh tỷ lệ và commit**

Require `962 >= 2 × 428`, sau đó chạy:

```bash
uv run validate_sparql_dataset
git diff --check
git add resources/dataset/main/train.jsonl resources/cases/rejection_checklist.json
git commit -m "Complete procedure first training coverage"
```

### Task 5: Mở rộng validation đủ 142 target

**Files:**
- Modify: `resources/dataset/main/val.jsonl`

**Interfaces:**
- Consumes: 142 target canonical trong train và validation đã audit.
- Produces: mọi target có mặt; target hướng dẫn có ít nhất hai câu; đăng ký học phần có bốn register.

- [ ] **Step 1: Tính deficit sau audit**

Đếm theo target canonical. Baseline trước audit cần thêm 102 câu; kết quả sau audit phải trong 85–120, nếu không thì dừng và báo cáo.

- [ ] **Step 2: Biên soạn đúng deficit với ID từ `question-004000`**

Mỗi target thiếu nhận một câu độc lập. Target hướng dẫn có một câu trực tiếp và một câu tổng quan. Đăng ký học phần có formal, neutral, colloquial, noisy.

- [ ] **Step 3: Xác minh và commit**

```bash
uv run validate_sparql_dataset
git diff --check
git add resources/dataset/main/val.jsonl
git commit -m "Cover every procedure target in validation"
```

### Task 6: Mở rộng và đóng băng test quy trình

**Files:**
- Modify: `resources/dataset/main/test.jsonl`
- Modify: `tests/research/test_dataset_content.py`

**Interfaces:**
- Consumes: 142 target canonical và test đã audit.
- Produces: test đủ target, contract tự động và checksum mới.

- [ ] **Step 1: Tính deficit và biên soạn test**

Baseline cần thêm 104 câu; kết quả sau audit phải trong 85–120. Dùng ID từ `question-005000`; không tái sử dụng cấu trúc câu validation vừa viết.

- [ ] **Step 2: Thêm contract procedure-first**

Mở rộng `PROCEDURE_FAMILIES` đủ 12 family và thêm test kiểm tra:

```python
def test_procedure_first_target_coverage() -> None:
    release = load_release()
    procedure = {
        split: [row for row in rows if row["query_id"].startswith("procedure-")]
        for split, rows in release.items()
    }
    train_counts = Counter(row["target"] for row in procedure["train"])
    instruction_targets = {
        row["target"] for row in procedure["train"]
        if row["query_id"] == "procedure-instruction"
    }
    assert len(train_counts) == 142
    assert min(train_counts.values()) >= 6
    assert all(train_counts[target] >= 10 for target in instruction_targets)
    required_registers = {"formal", "neutral", "colloquial", "noisy"}
    for target in train_counts:
        assert {
            row["register"] for row in procedure["train"] if row["target"] == target
        } == required_registers
    for target in instruction_targets:
        rows = [row for row in procedure["train"] if row["target"] == target]
        assert sum(row["query_id"] == "procedure-instruction" for row in rows) >= 6
        assert sum(row["query_id"] == "procedure-overview" for row in rows) >= 4

    course_target = (
        "SELECT ?answer WHERE { :CourseRegistrationProcedure "
        ":instructionProvision ?part . ?part :officialText ?answer . }"
    )
    assert train_counts[course_target] >= 12
    assert len(procedure["train"]) >= 2 * sum(
        row["query_id"] == "no-information" for row in release["train"]
    )
    for split in ("val", "test"):
        counts = Counter(row["target"] for row in procedure[split])
        assert set(train_counts) <= set(counts)
        assert all(counts[target] >= 2 for target in instruction_targets)
        for target in instruction_targets:
            query_ids = {
                row["query_id"] for row in procedure[split] if row["target"] == target
            }
            assert {"procedure-instruction", "procedure-overview"} <= query_ids
        course_rows = [row for row in procedure[split] if row["target"] == course_target]
        assert len(course_rows) >= 4
        assert {row["register"] for row in course_rows} == required_registers
```

- [ ] **Step 3: Khóa checksum sau khi contract qua**

Chỉ cập nhật `FROZEN_TEST_SHA256` sau khi validator và test procedure-first đều qua.

- [ ] **Step 4: Xác minh và commit**

```bash
uv run pytest -q tests/research/test_dataset.py tests/research/test_dataset_content.py tests/research/test_catalogue_validation.py tests/ontology/test_procedures_and_forms.py
git diff --check
git add resources/dataset/main/test.jsonl tests/research/test_dataset_content.py
git commit -m "Freeze procedure complete test coverage"
```

### Task 7: Sinh báo cáo và khóa dataset trước GPU

**Files:**
- Create: `reports/procedure-dataset.json`
- Regenerate: `resources/dataset/main/manifest.json`, `reports/dataset.json`, `reports/figures/*.svg`
- Modify: `README.md`, `docs/DATASET.md`, `docs/EVALUATION.md`, `resources/dataset/main/README.md`
- Modify only for measured assertions: `tests/research/test_reporting.py`, `tests/research/test_documentation_status.py`

**Interfaces:**
- Consumes: ba split hoàn tất và test đóng băng.
- Produces: dataset, manifest, báo cáo và tài liệu nhất quán; quyết định duy nhất liệu có được dùng GPU.

- [ ] **Step 1: Tạo `reports/procedure-dataset.json`**

Ghi số dòng theo split, 142 target, histogram mẫu/target, register/target, số target đạt ngưỡng, tỷ lệ procedure/OOD và SHA-256. Không ghi agent, stage hoặc version dataset.

- [ ] **Step 2: Sinh artifact bằng lệnh hiện có**

```bash
uv run generate_reports
```

Không sửa reporting code. Nếu lệnh lỗi, dừng và báo cáo lỗi.

- [ ] **Step 3: Đồng bộ tài liệu và assertion theo số đo thực tế**

Chỉ cập nhật hình dạng dataset, phân bố procedure-first, mục đích split, OOD và tiêu chí benchmark; không kể lịch sử phục hồi.

- [ ] **Step 4: Chạy cổng tĩnh duy nhất trước GPU**

```bash
uv run validate_sparql_dataset
uv run pytest -q
git diff --check
git status --short --branch
```

- [ ] **Step 5: Commit trạng thái đã khóa**

```bash
git add README.md docs/DATASET.md docs/EVALUATION.md resources/dataset/main/README.md resources/dataset/main/manifest.json reports/dataset.json reports/procedure-dataset.json reports/figures tests/research/test_reporting.py tests/research/test_documentation_status.py
git commit -m "Document the procedure first dataset"
```

### Task 8: Fine-tune T5Gemma2 đúng một lần và nghiệm thu

**Files:**
- Create ignored: `artifacts/procedure-recovery/t5gemma2/`
- Read only: dataset và manifest đã khóa.

**Interfaces:**
- Consumes: Task 7 xanh và base model local `google/t5gemma-2-270m-270m`.
- Produces: một best checkpoint, predictions và báo cáo đạt/không đạt.

- [ ] **Step 1: Preflight không thay code**

Xác nhận output directory rỗng, CUDA/BF16 khả dụng, model local tồn tại và manifest checksum đúng. Nếu lỗi, dừng.

- [ ] **Step 2: Chạy đúng một lần**

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True uv run train_sparql \
  --model t5gemma2 \
  --output-dir artifacts/procedure-recovery \
  --epochs 20 \
  --seed 42 \
  --save-model \
  --benchmark-after-training \
  --local-files-only
```

- [ ] **Step 3: Đánh giá contract**

Require: System Answer Exact toàn test ≥90%; procedure ≥95%; từng register quy trình ≥90%; câu người dùng cốt lõi 100%; false rejection hướng dẫn đăng ký học phần bằng 0; OOD safe rejection ≥94%.

- [ ] **Step 4: Báo cáo một lần rồi dừng**

Báo cáo runtime, best epoch, VRAM, validation, test, procedure theo register và toàn bộ câu procedure còn sai. Không sửa dataset, không train lần hai, không benchmark model khác và không test web.

## Explicitly Deferred

- Fine-tuning BARTpho và ViT5.
- CTranslate2 conversion, web application, UX và deployment.
- Ontology hoặc catalogue expansion.
- Hyperparameter tuning, seed khác hoặc vòng phục hồi thứ hai.
- Mọi refactor hoặc sửa script không trực tiếp nằm trong contract dataset.
