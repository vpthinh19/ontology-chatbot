# PEFT LoRA Training Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Huấn luyện BARTpho, ViT5 và T5Gemma2 bằng PEFT LoRA rồi lưu checkpoint Transformers đã merge để benchmark công bằng và chuyển model được chọn sang CTranslate2.

**Architecture:** `Seq2SeqTrainer` huấn luyện adapter PEFT trên base model đóng băng. Checkpoint validation chứa adapter; artifact cuối được merge thành model độc lập trước khi đánh giá và lưu.

**Tech Stack:** Python 3.12, Transformers 5.14, PEFT 0.20, PyTorch 2.13, pytest.

## Global Constraints

- Chỉ thay training/dependency/docs; không thay dataset, ontology, benchmark hoặc runtime trả lời.
- LoRA: rank 32, alpha 64, dropout 0, attention + MLP text encoder/decoder.
- Learning rate `1e-4`; seed, batch, scheduler, precision, padding và decoding giữ nguyên.
- Không Unsloth, TRL, QLoRA, `torch.compile` hoặc adapter trong runtime.

---

### Task 1: Khóa contract LoRA

**Files:**
- Modify: `tests/research/test_training.py`
- Modify: `src/ontchatbot/research/training.py`

**Interfaces:**
- Produces: `_lora_target_modules(model) -> list[str]` và hằng số cấu hình LoRA.

- [ ] Viết unit test cấu hình và target discovery.
- [ ] Chạy test để xác nhận thất bại do contract chưa tồn tại.
- [ ] Thêm implementation tối thiểu và chạy lại test.

### Task 2: Huấn luyện và merge PEFT

**Files:**
- Modify: `src/ontchatbot/research/training.py`
- Modify: `tests/research/test_training.py`

**Interfaces:**
- Consumes: target module và cấu hình Task 1.
- Produces: adapter checkpoint nội bộ và checkpoint `model/` đã merge.

- [ ] Viết test cho metadata, learning rate và trạng thái merge.
- [ ] Import PEFT trong train extra, gắn adapter sau khi nạp base model.
- [ ] Mở lại best adapter trên base pretrained, merge trước final evaluation.
- [ ] Ghi metadata LoRA vào `metrics.json` và chạy test training.

### Task 3: Dependency và tài liệu

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `README.md`
- Modify: `docs/TRAINING.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/DEPLOYMENT.md`

**Interfaces:**
- Produces: môi trường train có PEFT trực tiếp; runtime vẫn chỉ dùng model CT2.

- [ ] Giữ `transformers` trong inference extra và thêm `peft` vào train extra.
- [ ] Mô tả LoRA, merge và checkpoint lifecycle bằng ngôn ngữ trạng thái cuối.
- [ ] Chạy test tài liệu và kiểm tra lockfile.

### Task 4: Nghiệm thu

**Files:**
- Read only: toàn bộ code/test đã đổi.
- Create ignored then remove: artifact smoke test.

**Interfaces:**
- Produces: bằng chứng unit test và smoke train qua.

- [ ] Chạy `uv run pytest tests/research/test_training.py -q`.
- [ ] Chạy toàn bộ `uv run pytest -q`.
- [ ] Chạy smoke train ba model local, không benchmark test.
- [ ] Xác minh không còn process GPU/artifact tạm và commit từng phần.
