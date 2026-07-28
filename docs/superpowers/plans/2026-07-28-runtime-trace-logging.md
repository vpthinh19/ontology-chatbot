# Runtime Trace Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ghi trace terminal đầy đủ cho từng lượt chat để nhìn thấy quyết định gate, SPARQL model sinh, kết quả ontology, reply và stage gây lỗi.

**Architecture:** `OntologyChatbot` là nơi duy nhất điều phối và ghi log cấp request bằng standard-library `logging`; các module gate, generator và SPARQL vẫn giữ trách nhiệm hiện tại. CLI cấu hình log level/formatter trước khi nạp model và chạy Uvicorn.

**Tech Stack:** Python 3.12, standard-library `logging`, `time.perf_counter`, `uuid`, pytest `caplog`, CTranslate2, RDFLib, FastAPI.

## Global Constraints

- Mỗi request có một `request_id` chung cho toàn bộ dòng log.
- Mức `INFO` ghi input gốc/chuẩn hoá, probability/threshold/decision gate, SPARQL, số dòng, reply và latency.
- Mức `ERROR` ghi stage, request ID và stack trace rồi re-raise lỗi gốc.
- Gate từ chối không gọi hoặc ghi log generator/ontology.
- Không log token ID, hidden state, logits thô; không thêm dependency hay file handler.
- `serve_sparql --log-level` mặc định `info`.
- Không sửa ontology, dataset, model artifact hoặc response HTTP.
- Không stage `.gitignore`, `resources/ontology/ontology_v9.properties`, `uv.lock`, `test.html`, `test_phobert.py`, `test_preprocess.py`.

---

### Task 1: Trace pipeline theo từng stage

**Files:**
- Modify: `src/ontchatbot/runtime/gate.py`
- Modify: `src/ontchatbot/runtime/pipeline.py`
- Modify: `tests/runtime/test_inference.py`

**Interfaces:**
- Consumes: `DomainGate.decide(text: str) -> GateDecision`
- Produces: `DomainGate.threshold: float`
- Produces: loggers under `ontchatbot.runtime.pipeline`

- [ ] **Step 1: Viết test fail cho nhánh gate từ chối**

Test dùng `caplog.at_level(logging.INFO, logger="ontchatbot.runtime.pipeline")`, gate có `threshold=0.75` và trả `GateDecision(False, 0.2)`. Assert log có input chuẩn hoá, `probability=0.200000`, `threshold=0.750000`, `accepted=false`; assert không có `generator` và generator không được gọi.

- [ ] **Step 2: Chạy test RED**

Run:

```bash
uv run --frozen pytest tests/runtime/test_inference.py::test_chatbot_logs_rejected_gate_decision -q
```

Expected: FAIL vì pipeline chưa ghi trace.

- [ ] **Step 3: Viết test fail cho success và exception**

Success test dùng graph thật và query `AcademicLeaveProcedure :handledBy`; assert log có SPARQL nguyên văn, `ontology rows=1`, reply và `total_ms`. Exception test cho generator raise `RuntimeError("boom")`; assert `caplog` có `stage=generator`, `ERROR` và `exc_info`.

- [ ] **Step 4: Implement logging tối thiểu trong pipeline**

Trong `pipeline.py`, dùng `uuid.uuid4().hex[:12]`, `time.perf_counter()` và module logger. Log bằng placeholder `%s/%r` để tránh format khi level bị tắt. Bọc toàn bộ luồng trong `try/except`, cập nhật biến `stage` trước gate, generator, ontology và renderer; `logger.exception("request=%s stage=%s failed", request_id, stage)` rồi `raise`.

Pipeline phải lưu rows trước khi render:

```python
rows = execute_select(self.graph, query)
logger.info("request=%s ontology rows=%d duration_ms=%.1f", ...)
reply = render_rows(rows)
```

Trong `gate.py`, thêm property `threshold` vào `DomainGate` protocol để pipeline không đọc private state.

- [ ] **Step 5: Chạy focused tests GREEN**

```bash
uv run --frozen pytest tests/runtime/test_inference.py tests/runtime/test_gate.py tests/runtime/test_serve.py -q
```

Expected: tất cả PASS.

- [ ] **Step 6: Commit pipeline trace**

```bash
git add src/ontchatbot/runtime/gate.py src/ontchatbot/runtime/pipeline.py tests/runtime/test_inference.py
git commit -m "Add runtime request tracing"
```

### Task 2: Cấu hình CLI và nghiệm thu log thật

**Files:**
- Modify: `src/ontchatbot/cli/serve.py`
- Modify: `tests/runtime/test_serve_cli.py`
- Modify: `docs/DEPLOYMENT.md`

**Interfaces:**
- Produces CLI argument: `--log-level {debug,info,warning,error}`
- Produces: `_configure_logging(level: str) -> None`

- [ ] **Step 1: Viết test fail cho CLI logging**

Assert `_parse_args([...])` mặc định trả `log_level == "info"`; truyền `--log-level debug` trả `debug`. Monkeypatch `logging.basicConfig` và assert `_configure_logging("warning")` gọi với `level=logging.WARNING`, formatter có timestamp/level/logger/message.

- [ ] **Step 2: Chạy test RED**

```bash
uv run --frozen pytest tests/runtime/test_serve_cli.py -q
```

Expected: FAIL vì argument và helper chưa tồn tại.

- [ ] **Step 3: Implement CLI logging tối thiểu**

Thêm argument lowercase với bốn choice, gọi `_configure_logging(args.log_level)` trước `_load_chatbot(args)`. Dùng:

```python
logging.basicConfig(
    level=getattr(logging, level.upper()),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
```

- [ ] **Step 4: Cập nhật deployment guide**

Ghi `--log-level info` trong lệnh serve và một đoạn trace mẫu giải thích gate/SPARQL/rows/reply; không đưa lịch sử phát triển vào tài liệu.

- [ ] **Step 5: Chạy focused và full tests**

```bash
uv run --frozen --extra inference pytest tests/runtime -q
uv run --frozen --extra inference pytest -q
git diff --check
```

Expected: toàn bộ PASS, diff sạch whitespace.

- [ ] **Step 6: Chạy web thật với các câu trong `test.html`**

Khởi động CPU INT8 với `--log-level info`, gửi bảy câu trong nhật ký và xác nhận mỗi request có probability/threshold; request được nhận có SPARQL/rows/reply; câu bị reject không có generator log. Dừng server và bảo đảm không còn process mồ côi.

- [ ] **Step 7: Commit CLI và tài liệu**

```bash
git add src/ontchatbot/cli/serve.py tests/runtime/test_serve_cli.py docs/DEPLOYMENT.md
git commit -m "Configure chatbot trace logging"
```
