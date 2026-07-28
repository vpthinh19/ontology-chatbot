# Input Normalization and Fallback UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bổ sung whitelist viết tắt chắc nghĩa, thống nhất phản hồi `Không có thông tin.` và lưu nguyên văn các câu hỏi thực tế trong khi chờ xây lại ontology/dataset.

**Architecture:** `normalize_model_input` vẫn là normalizer duy nhất cho gate và generator. Runtime dùng một hằng số phản hồi chung; chỉ các lỗi gate/query dự kiến được đổi thành HTTP 200, còn lỗi lập trình tiếp tục nổi lên. Các câu hỏi thủ công nằm ngoài dataset hiện hành trong một file văn bản đơn giản.

**Tech Stack:** Python 3.11+, `re`, FastAPI, RDFLib, pytest.

## Global Constraints

- Không sửa ontology, `resources/dataset/main` hoặc `resources/dataset/gate`.
- Không fine-tuning, benchmark, convert model hoặc sửa script nghiên cứu.
- Không word segmentation, fuzzy matching, entity extraction hoặc intent rules trong preprocessing.
- `hp` luôn được chuẩn hoá thành `học phần`.
- Phản hồi giao diện chính xác là `Không có thông tin.`.
- Không che lỗi khởi động, lỗi nạp artifact hoặc lỗi lập trình ngoài lỗi query dự kiến.
- Không stage `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `test.html`, `test_phobert.py`, `test_preprocess.py`.

---

### Task 1: Mở rộng normalizer bằng whitelist chắc nghĩa

**Files:**
- Modify: `tests/runtime/test_model_text.py`
- Modify: `src/ontchatbot/runtime/text.py`

**Interfaces:**
- Consumes: `normalize_model_input(text: str) -> str` hiện có.
- Produces: cùng interface, thêm ánh xạ token nhưng vẫn idempotent.

- [ ] **Step 1: Viết test thất bại cho viết tắt miền học vụ**

Thêm các assertion bao phủ `hp`, `đk`, `đkhp`, `dkmh`, `ctdt`, `cvht`, `gdtc`,
`gdqp`, `gpa`, `kqht`, `mh`, `bl` và `pdt`. Sửa test cũ đang kỳ vọng `dk hp`
được giữ nguyên:

```python
def test_expand_additional_academic_abbreviations() -> None:
    source = "đk hp, ĐKHP, dkmh, CTDT, cvht, GDTC, gdqp, GPA, KQHT, MH, BL, PDT"
    assert normalize_model_input(source) == (
        "đăng ký học phần, đăng ký học phần, đăng ký môn học, "
        "chương trình đào tạo, cố vấn học tập, giáo dục thể chất, "
        "giáo dục quốc phòng, điểm trung bình, kết quả học tập, "
        "môn học, bảo lưu, phòng đào tạo"
    )
```

- [ ] **Step 2: Viết test thất bại cho chat spelling chắc nghĩa và trường hợp đa nghĩa**

```python
def test_expand_conservative_chat_spellings() -> None:
    source = "khong bik đc hp lam thnao, bjo hoc, trc do vs ai, cx rui"
    assert normalize_model_input(source) == (
        "không biết được học phần làm thế nào, bao giờ học, "
        "trước do với ai, cũng rồi"
    )


def test_preserve_excluded_ambiguous_tokens() -> None:
    source = "bn hk bg m h v g ng nh ck"
    assert normalize_model_input(source) == "bao nhiêu hk bg m h v g ng nh ck"
```

`bn` giữ nghĩa hiện hành là `bao nhiêu`; các token còn lại không được bổ sung.

- [ ] **Step 3: Chạy test để xác nhận RED**

Run: `pytest tests/runtime/test_model_text.py -q`

Expected: FAIL tại các ánh xạ mới.

- [ ] **Step 4: Bổ sung tối thiểu vào `_ABBREVIATIONS`**

Thêm chính xác các khóa trong đặc tả vào mapping hiện có. Tiếp tục dùng
`_ABBREVIATION` với ranh giới token và `casefold`; không mang URL/email cleanup,
repeat collapsing hoặc matching ontology từ `test_preprocess.py` sang.

- [ ] **Step 5: Chạy test để xác nhận GREEN và idempotence**

Run: `pytest tests/runtime/test_model_text.py -q`

Expected: toàn bộ test pass, bao gồm `test_normalization_is_idempotent`.

- [ ] **Step 6: Commit riêng Task 1**

```bash
git add src/ontchatbot/runtime/text.py tests/runtime/test_model_text.py
git commit -m "Expand conservative input normalization"
```

---

### Task 2: Thống nhất phản hồi dự phòng mà không che lỗi hệ thống

**Files:**
- Modify: `src/ontchatbot/runtime/render.py`
- Modify: `src/ontchatbot/runtime/model.py`
- Modify: `src/ontchatbot/runtime/pipeline.py`
- Modify: `src/ontchatbot/runtime/api.py`
- Modify: `tests/runtime/test_render.py`
- Modify: `tests/runtime/test_inference.py`
- Modify: `tests/runtime/test_serve.py`

**Interfaces:**
- Produces: `NO_INFORMATION_REPLY: str = "Không có thông tin."` trong `runtime.render`.
- Produces: `QueryGenerationError(ValueError)` trong `runtime.model` cho đầu ra model rỗng.
- Consumes: `SparqlError`, `OutOfScopeError`, `QueryGenerationError` là ba lỗi query dự kiến tại API.

- [ ] **Step 1: Viết test thất bại cho kết quả rỗng và model rỗng**

Đổi kỳ vọng renderer:

```python
def test_render_empty_rows() -> None:
    assert render_rows([]) == "Không có thông tin."
```

Trong test inference, xác nhận generator ném lỗi có kiểu riêng:

```python
with pytest.raises(QueryGenerationError, match="empty query"):
    generator.generate("học phí")
```

- [ ] **Step 2: Viết test API thất bại cho ba đường dự kiến và lỗi bất ngờ**

Test riêng cho `OutOfScopeError`, `QueryGenerationError` và `SparqlError` phải
trả HTTP 200:

```python
assert response.status_code == 200
assert response.json() == {"reply": NO_INFORMATION_REPLY}
```

Thêm test chatbot ném `RuntimeError("boom")`; khi ASGI transport không chủ động
raise app exception, response phải là HTTP 500. Điều này chứng minh lỗi hệ thống
không bị đổi thành “Không có thông tin.”.

- [ ] **Step 3: Chạy test để xác nhận RED**

Run: `pytest tests/runtime/test_render.py tests/runtime/test_inference.py tests/runtime/test_serve.py -q`

Expected: FAIL vì copy và kiểu lỗi cũ.

- [ ] **Step 4: Thêm hằng số và kiểu lỗi tối thiểu**

Trong `render.py`:

```python
NO_INFORMATION_REPLY = "Không có thông tin."
```

`render_rows([])` trả hằng số đó. Trong `model.py`:

```python
class QueryGenerationError(ValueError):
    """The model did not produce a usable query string."""
```

Chỉ thay lỗi đầu ra model rỗng bằng `QueryGenerationError("model generated an empty query")`.

- [ ] **Step 5: Nối các lỗi dự kiến vào API**

`pipeline.py` nhập `NO_INFORMATION_REPLY`, dùng nó làm message của
`OutOfScopeError` và bỏ `OUT_OF_SCOPE_REPLY`. `api.py` bắt đúng:

```python
except (OutOfScopeError, QueryGenerationError, SparqlError):
    return {"reply": NO_INFORMATION_REPLY}
```

Không bắt `ValueError` tổng quát và không bắt `Exception`.

- [ ] **Step 6: Chạy test runtime để xác nhận GREEN**

Run: `pytest tests/runtime/test_render.py tests/runtime/test_inference.py tests/runtime/test_serve.py tests/runtime/test_query_engine.py -q`

Expected: toàn bộ test pass.

- [ ] **Step 7: Commit riêng Task 2**

```bash
git add src/ontchatbot/runtime/render.py src/ontchatbot/runtime/model.py \
  src/ontchatbot/runtime/pipeline.py src/ontchatbot/runtime/api.py \
  tests/runtime/test_render.py tests/runtime/test_inference.py \
  tests/runtime/test_serve.py
git commit -m "Unify no-information responses"
```

---

### Task 3: Giữ lại ca sử dụng thực tế và đồng bộ tài liệu

**Files:**
- Create: `resources/cases/user_queries.txt`
- Modify: `docs/CONCEPT.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/DATASET.md`

**Interfaces:**
- Produces: file UTF-8, mỗi dòng một câu nguyên văn, không có label/SPARQL.
- Consumes: không có; file này không tham gia loader dataset hoặc training.

- [ ] **Step 1: Ghi các câu đã có trong phiên test giao diện**

Từ `test.html`, ghi mỗi tin nhắn người dùng duy nhất thành một dòng. Tối thiểu
phải chứa nguyên văn:

```text
chào bạn nha
đăng ký hc phần như nào nhỉ
đăng ký học phần sao
vì sao lại đăng ký học phần
đk hc phần như thế nào
hc phí k65 cntt
học phí k67 như thế nào
```

Không thêm câu trả lời, nhãn gate hay SPARQL khi chưa có ontology mới.

- [ ] **Step 2: Đồng bộ tài liệu công khai**

- `CONCEPT.md`: ba đường query dự kiến cùng hiển thị `Không có thông tin.`.
- `DEPLOYMENT.md`: cập nhật ví dụ gate rejection và giải thích log vẫn giữ nguyên nhân.
- `DATASET.md`: giải thích `resources/cases/user_queries.txt` chỉ là nguồn ca hồi quy
  cho lần xây dataset mới, không thuộc split hiện tại.

- [ ] **Step 3: Kiểm tra file ca sử dụng không bị loader hiểu là dataset**

Run: `pytest tests/research/test_dataset.py tests/research/test_gate_dataset.py -q`

Expected: toàn bộ test pass; không có thay đổi record count.

- [ ] **Step 4: Commit riêng Task 3**

```bash
git add resources/cases/user_queries.txt docs/CONCEPT.md docs/DEPLOYMENT.md docs/DATASET.md
git commit -m "Preserve real user query cases"
```

---

### Task 4: Xác minh toàn bộ thay đổi

**Files:**
- Verify only; không tạo artifact.

**Interfaces:**
- Consumes: ba task đã commit.
- Produces: bằng chứng test và worktree sạch ngoài file người dùng sở hữu.

- [ ] **Step 1: Chạy toàn bộ test đúng một lần**

Run: `pytest -q`

Expected: toàn bộ test pass.

- [ ] **Step 2: Kiểm tra whitespace và phạm vi Git**

Run: `git diff --check && git status --short`

Expected: không có whitespace error; chỉ còn các file người dùng sở hữu đã liệt
kê trong Global Constraints.

- [ ] **Step 3: Không chạy công việc nặng ngoài phạm vi**

Không chạy fine-tuning, benchmark, conversion, server lâu dài hoặc sinh cache/artifact.
