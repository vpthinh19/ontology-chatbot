# Candidate Dataset Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đồng bộ toàn bộ tài liệu đang hoạt động để ontology chưa bị tuyên bố canonical và corpus 456 câu chỉ được mô tả là candidate pool dùng cho smoke/curation.

**Architecture:** README và các phụ lục công khai cùng dùng một vocabulary trạng thái: lớp nguồn ontology đã kiểm chứng, semantic index đang audit, catalogue/dataset hiện tại là candidate, full fine-tuning và benchmark chính thức chưa được phép. Các đặc tả/kế hoạch cũ được giữ làm lịch sử kỹ thuật nhưng có notice chỉ tới đặc tả readiness mới.

**Tech Stack:** Markdown, pytest, ripgrep, Git.

## Global Constraints

- Không sửa ontology, catalogue, JSONL, manifest, trainer hoặc artifact model.
- Không đổi đường dẫn `resources/dataset/main/`; `main` chỉ tên dataset hợp nhất cho một model, không phải chứng nhận production.
- Giữ 456 câu hiện tại làm candidate pool; không tự động công nhận bản ghi nào là official.
- Không công bố metric pilot như benchmark chính thức.
- Không stage `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `NTUdocs/`, `bieumau_url.html`, `test.html`, `test_phobert.py` hoặc `test_preprocess.py`.
- Nguồn quyết định là `docs/superpowers/specs/2026-07-29-ontology-dataset-readiness-design.md`.

---

### Task 1: Khóa vocabulary trạng thái bằng test tài liệu

**Files:**
- Create: `tests/research/test_documentation_status.py`

**Interfaces:**
- Consumes: các file Markdown công khai và notice trong đặc tả/kế hoạch cũ.
- Produces: regression test ngăn corpus 456 câu bị gọi lại là release production và ngăn full fine-tuning bị mô tả là bước hiện tại.

- [ ] **Step 1: Viết test trạng thái ban đầu**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_public_docs_call_current_dataset_candidate() -> None:
    files = (
        "README.md",
        "docs/DATASET.md",
        "docs/TRAINING.md",
        "resources/dataset/main/README.md",
        "reports/README.md",
    )
    joined = "\n".join(_read(path) for path in files)
    assert "candidate pool" in joined
    assert "Release hiện có 456 câu" not in joined
    assert "# Dataset production" not in joined
    assert "release chính thức này" not in joined


def test_public_docs_block_official_training_until_readiness_gates_pass() -> None:
    training = _read("docs/TRAINING.md")
    readme = _read("README.md")
    assert "không được full fine-tune" in training
    assert "ontology → catalogue → dataset" in readme
    assert "semantic index" in readme


def test_superseded_designs_point_to_current_readiness_spec() -> None:
    replacement = "2026-07-29-ontology-dataset-readiness-design.md"
    files = (
        "docs/superpowers/specs/2026-07-29-official-production-dataset-design.md",
        "docs/superpowers/plans/2026-07-29-official-production-dataset.md",
        "docs/superpowers/specs/2026-07-29-official-ontology-refactor-design.md",
        "docs/superpowers/plans/2026-07-29-official-ontology-refactor.md",
    )
    for path in files:
        assert replacement in _read(path)
```

- [ ] **Step 2: Chạy test và xác nhận trạng thái cũ làm test fail**

Run: `uv run pytest tests/research/test_documentation_status.py -q`

Expected: FAIL vì README/docs còn gọi 456 câu là release production và các plan cũ chưa có notice thay thế.

- [ ] **Step 3: Commit regression test**

```bash
git add tests/research/test_documentation_status.py
git commit -m "Test candidate dataset documentation status"
```

### Task 2: Đồng bộ tài liệu công khai

**Files:**
- Modify: `README.md`
- Modify: `docs/CONCEPT.md`
- Modify: `docs/ONTOLOGY.md`
- Modify: `docs/DATASET.md`
- Modify: `docs/TRAINING.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `resources/dataset/main/README.md`
- Modify: `reports/README.md`

**Interfaces:**
- Consumes: vocabulary trạng thái trong đặc tả readiness và số liệu snapshot hiện tại.
- Produces: tài liệu đọc độc lập, phân biệt điều đã kiểm chứng, candidate và công việc chưa được phép thực hiện.

- [ ] **Step 1: Sửa README thành nguồn trạng thái tổng quan**

Thêm mục `Trạng thái hiện tại` ngay sau phần mở đầu với đúng bốn trạng thái:

```text
Đã kiểm chứng: lớp nguồn ontology và contract runtime.
Đang nghiệm thu: semantic index và inventory khả năng trả lời.
Candidate: catalogue cùng 456 câu hiện tại.
Chưa thực hiện: full fine-tuning, benchmark chính thức và chọn model production.
```

Đổi phần Dataset để gọi các con số 456/340/58/58 là snapshot candidate. Thêm
chiều coverage bắt buộc `ontology → catalogue → dataset`; không tuyên bố finite
slot hiện tại đồng nghĩa phủ toàn ontology.

- [ ] **Step 2: Sửa tài liệu ontology và concept**

Trong `docs/ONTOLOGY.md`, tách `lớp nguồn đã kiểm chứng` khỏi `semantic index
đang audit`, liệt kê Điều 20, 29, 30 và `ClassAbsenceRequestProcedure` là các
quyết định phải chốt trước khi khóa IRI. Trong `docs/CONCEPT.md`, giữ kiến trúc
một model nhưng ghi rõ catalogue/dataset chỉ được xây sau inventory answer
surface, không suy phạm vi từ candidate hiện tại.

- [ ] **Step 3: Viết lại trạng thái dataset**

Trong `docs/DATASET.md` và `resources/dataset/main/README.md`:

- đổi tiêu đề/định nghĩa production thành candidate pool;
- giữ số liệu 456 câu để mô tả snapshot vật lý hiện tại;
- nói rõ từng bản ghi sẽ được giữ/sửa/loại sau ontology/catalogue audit;
- thêm coverage matrix `query family × entity/slot × wording × register × split`;
- yêu cầu lượng lớn ngoài miền theo checklist đa dạng thay vì sinh câu vô nghĩa;
- giữ input raw và dùng chung `normalize_model_input` trong trainer/benchmark/runtime;
- ghi rõ `test.html` là nguồn ca người dùng, không phải nguồn dữ kiện ontology.

- [ ] **Step 4: Chặn hiểu nhầm về training, evaluation và deployment**

Trong `docs/TRAINING.md`, đặt một gate trước cấu hình benchmark:

```text
Với candidate pool hiện tại chỉ cho phép smoke/pilot có giới hạn. Không được
full fine-tune, chọn checkpoint chính thức hoặc benchmark test cho đến khi ba
cổng ontology, catalogue và dataset được nghiệm thu.
```

Trong `docs/EVALUATION.md` và `docs/DEPLOYMENT.md`, ghi rõ metric và quy trình
artifact là giao thức tương lai; chúng không mô tả checkpoint production hiện
có. Không thay đổi định nghĩa metric đã chốt.

- [ ] **Step 5: Sửa mô tả report**

Trong `reports/README.md`, giải thích `training_readiness.ready` hiện chỉ có
nghĩa candidate vượt các kiểm tra tĩnh nội bộ catalogue, không có nghĩa ontology
coverage hoàn tất hoặc dataset sẵn sàng full fine-tuning. Ghi rõ
`reports/dataset.json` là snapshot candidate và sẽ được thay sau khi reporting
contract có inventory coverage.

- [ ] **Step 6: Chạy hai regression test tài liệu công khai**

Run:

```bash
uv run pytest \
  tests/research/test_documentation_status.py::test_public_docs_call_current_dataset_candidate \
  tests/research/test_documentation_status.py::test_public_docs_block_official_training_until_readiness_gates_pass \
  -q
```

Expected: PASS. Test notice vẫn đỏ cho đến Task 3.

- [ ] **Step 7: Commit tài liệu công khai**

```bash
git add README.md docs/CONCEPT.md docs/ONTOLOGY.md docs/DATASET.md docs/TRAINING.md docs/EVALUATION.md docs/DEPLOYMENT.md resources/dataset/main/README.md reports/README.md
git commit -m "Mark the current dataset as a candidate pool"
```

### Task 3: Đánh dấu kế hoạch cũ đã bị thay thế

**Files:**
- Modify: `docs/superpowers/specs/2026-07-29-official-production-dataset-design.md`
- Modify: `docs/superpowers/plans/2026-07-29-official-production-dataset.md`
- Modify: `docs/superpowers/specs/2026-07-29-official-ontology-refactor-design.md`
- Modify: `docs/superpowers/plans/2026-07-29-official-ontology-refactor.md`

**Interfaces:**
- Consumes: đường dẫn đặc tả readiness canonical.
- Produces: notice lịch sử không thể bị hiểu nhầm là trạng thái/tiêu chí nghiệm thu hiện tại.

- [ ] **Step 1: Thêm notice ngay dưới tiêu đề bốn file cũ**

Dùng cùng một nội dung, điều chỉnh danh từ ontology/dataset khi cần:

```markdown
> **Trạng thái:** Tài liệu này ghi lại lần triển khai đã tạo lớp nguồn ontology
> hoặc candidate pool. Nó không còn là tiêu chí nghiệm thu canonical. Xem
> [đặc tả readiness](../specs/2026-07-29-ontology-dataset-readiness-design.md).
```

Đối với file trong `specs/`, link dùng tên file cùng thư mục:
`2026-07-29-ontology-dataset-readiness-design.md`.

- [ ] **Step 2: Chạy test notice**

Run: `uv run pytest tests/research/test_documentation_status.py -q`

Expected: PASS.

- [ ] **Step 3: Commit notice kế hoạch cũ**

```bash
git add docs/superpowers/specs/2026-07-29-official-production-dataset-design.md docs/superpowers/plans/2026-07-29-official-production-dataset.md docs/superpowers/specs/2026-07-29-official-ontology-refactor-design.md docs/superpowers/plans/2026-07-29-official-ontology-refactor.md
git commit -m "Supersede premature production readiness plans"
```

### Task 4: Nghiệm thu batch tài liệu

**Files:**
- Modify only if verification exposes a contradiction in files listed by Tasks 1–3.

**Interfaces:**
- Consumes: toàn bộ thay đổi tài liệu và regression test.
- Produces: bằng chứng tài liệu không còn tuyên bố candidate là production.

- [ ] **Step 1: Chạy test tài liệu và report hiện có**

Run: `uv run pytest tests/research/test_documentation_status.py tests/research/test_reporting.py -q`

Expected: PASS.

- [ ] **Step 2: Quét cụm từ trạng thái cũ trong tài liệu đang hoạt động**

Run:

```bash
rg -n "Release hiện có 456 câu|# Dataset production|release chính thức này" README.md docs resources/dataset/main reports -g '!docs/superpowers/**'
```

Expected: không có kết quả.

- [ ] **Step 3: Kiểm tra diff và phạm vi Git**

Run: `git diff --check`

Run: `git status --short`

Expected: diff sạch; chỉ file thuộc plan được commit, các file người dùng trong Global Constraints vẫn giữ nguyên trạng thái trước task.
