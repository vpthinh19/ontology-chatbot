# Unified Model Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đồng bộ toàn bộ tài liệu hiện hành sang kiến trúc một model seq2seq xử lý cả trong và ngoài miền, trước khi xây ontology/dataset từ tài liệu chính thức.

**Architecture:** Tài liệu mô tả kiến trúc đích, không khẳng định code/artifact cũ đã triển khai thiết kế mới. README và các phụ lục công khai không giữ số liệu ontology, dataset hay benchmark cũ; đặc tả thống nhất ngày 2026-07-28 là nguồn quyết định kỹ thuật.

**Tech Stack:** Markdown, Mermaid, SPARQL, Git.

## Global Constraints

- Không sửa code, ontology, dataset, artifact, report hoặc dependency.
- Output model chỉ là một dòng `SELECT ...` hoặc `không có thông tin`.
- Câu hỗn hợp có ít nhất một yêu cầu không hỗ trợ phải bị từ chối toàn bộ.
- Chỉ còn dataset chính và ba model BARTpho, ViT5, T5Gemma2.
- Không công bố lại số liệu cũ như kết quả của kiến trúc mới.
- Không để placeholder số liệu; bỏ hẳn phần chưa có kết quả.
- Không stage `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `test.html`, `test_phobert.py`, `test_preprocess.py`.

---

### Task 1: Đồng bộ tài liệu tổng quan và ontology

**Files:**
- Modify: `README.md`
- Modify: `docs/CONCEPT.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ONTOLOGY.md`

**Interfaces:**
- Consumes: contract trong `docs/superpowers/specs/2026-07-28-unified-seq2seq-domain-handling-design.md`.
- Produces: mô tả kiến trúc đích không còn PhoBERT/domain gate.

- [ ] **Step 1: Viết lại README không dùng số liệu cũ**

Giữ bài toán, luồng một model, hai dạng output, vai trò ontology, ba model và
metric dự kiến. Nêu rõ ontology/dataset đang được xây từ tài liệu chính thức;
không giữ bảng 2.263 câu, 215 query, benchmark cũ hoặc metric PhoBERT.

- [ ] **Step 2: Viết lại concept và architecture**

Mermaid phải thể hiện:

```text
input → normalize → seq2seq → marker/SELECT → validator → RDFLib → renderer
```

Xoá `DomainGate`, PhoBERT, threshold, classifier head, dataset gate và artifact
gate. Ghi rõ câu hỗn hợp bị từ chối toàn bộ.

- [ ] **Step 3: Chuyển ONTOLOGY thành contract cho nguồn chính thức**

Giữ quy ước IRI tiếng Anh, label tiếng Việt, altLabel và vai trò object/datatype
property. Xoá số lượng class/property/individual và danh sách dữ liệu cụ thể của
ontology cũ. Nêu thứ tự: tài liệu chính thức → ontology → query catalogue → dataset.

- [ ] **Step 4: Kiểm tra từ khoá cũ trong nhóm tài liệu**

Run:

```bash
rg -n "PhoBERT|domain gate|dataset/gate|2\.263|215 truy vấn|95,58|1,16" \
  README.md docs/CONCEPT.md docs/ARCHITECTURE.md docs/ONTOLOGY.md
```

Expected: không có kết quả.

---

### Task 2: Đồng bộ dataset, training, evaluation và deployment

**Files:**
- Modify: `docs/DATASET.md`
- Modify: `docs/TRAINING.md`
- Modify: `docs/EVALUATION.md`
- Modify: `docs/DEPLOYMENT.md`
- Modify: `docs/specs/production-dataset.md`

**Interfaces:**
- Produces: schema dataset hợp nhất và giao thức benchmark ba model.
- Consumes: marker `không có thông tin` và phản hồi UI `Không có thông tin.`.

- [ ] **Step 1: Viết lại DATASET và production spec**

Chỉ mô tả `resources/dataset/main/{train,val,test}.jsonl`. Câu trong miền có
target SPARQL; câu ngoài miền và câu hỗn hợp có target marker. Ghi rõ các câu
trong `resources/cases/user_queries.txt` phải được gán lại từ ontology mới.

- [ ] **Step 2: Xoá gate training khỏi TRAINING**

Giữ giao thức công bằng đã chốt cho ba seq2seq model. Nêu rằng dữ liệu ngoài
miền làm tăng số mẫu nhưng không tạo model/classifier thứ tư. Bỏ toàn bộ lệnh
và hyperparameter PhoBERT.

- [ ] **Step 3: Viết lại EVALUATION**

Giữ In-domain Answer Exact và metric SPARQL. Bổ sung marker exact, false
acceptance, mixed-query rejection và System Answer Exact tách theo nhóm. Xoá
metric, threshold và ma trận của PhoBERT.

- [ ] **Step 4: Viết DEPLOYMENT theo contract một artifact**

Chỉ mô tả convert một model seq2seq và runtime một artifact. Không ghi câu lệnh
khởi động chưa được code hiện tại hỗ trợ; ghi rõ CLI được cập nhật ở bước
implementation sau. Log cần chứa output model thay cho probability gate.

- [ ] **Step 5: Kiểm tra từ khoá và số liệu cũ**

Run:

```bash
rg -n "PhoBERT|domain gate|dataset/gate|gate-model|threshold|2\.263|4\.526|215 target|430 câu" \
  docs/DATASET.md docs/TRAINING.md docs/EVALUATION.md docs/DEPLOYMENT.md \
  docs/specs/production-dataset.md
```

Expected: không có kết quả.

---

### Task 3: Dọn đặc tả gate lỗi thời và xác minh tài liệu

**Files:**
- Delete: `docs/specs/2026-07-28-ct2-domain-gate-runtime.md`
- Delete: `docs/specs/2026-07-28-phobert-domain-gate-design.md`
- Delete: `docs/superpowers/plans/2026-07-28-ct2-domain-gate-runtime.md`
- Delete: `docs/superpowers/plans/2026-07-28-phobert-domain-gate.md`
- Modify: `docs/superpowers/specs/2026-07-28-runtime-trace-logging-design.md`
- Modify: `docs/superpowers/specs/2026-07-28-input-normalization-and-fallback-design.md`

**Interfaces:**
- Produces: không còn đặc tả hiện hành nào yêu cầu gate riêng.

- [ ] **Step 1: Xoá bốn tài liệu chỉ phục vụ PhoBERT gate**

Không xoá code/artifact trong task tài liệu này.

- [ ] **Step 2: Cập nhật hai đặc tả còn hiệu lực**

Logging ghi `model output=` thay cho gate probability. Fallback dùng marker,
query lỗi hoặc kết quả rỗng; preprocessing vẫn giữ nguyên whitelist.

- [ ] **Step 3: Kiểm tra link Markdown local**

Run một script chỉ đọc để phân giải mọi link tương đối trong `README.md` và
`docs/**/*.md`; expected không có link thiếu.

- [ ] **Step 4: Kiểm tra whitespace và toàn bộ dấu vết gate trong tài liệu hiện hành**

Run:

```bash
git diff --check -- README.md docs
rg -n "PhoBERT|domain gate|dataset/gate|gate-model-dir|classifier\.npz" README.md docs \
  --glob '!docs/superpowers/plans/2026-07-28-unified-model-documentation.md'
```

Expected: không có whitespace error và không có mô tả gate còn sót.

- [ ] **Step 5: Commit toàn bộ thay đổi tài liệu, không stage file người dùng**

```bash
git add README.md docs resources/cases/user_queries.txt
git commit -m "Document unified seq2seq architecture"
```

Trước commit, kiểm tra `git diff --cached --name-only` không chứa bất kỳ file
ngoài danh sách tài liệu và `resources/cases/user_queries.txt`.
