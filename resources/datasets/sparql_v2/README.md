# Dataset SPARQL v2 — working draft

`draft.jsonl` là đầu vào đã hoàn tất semantic review Stage B, chưa phải release
train/val/test cuối cùng.

- Nguồn chỉ gồm train và validation của v1.
- Test v1 là audit-only và không được sao chép vào draft.
- Target đã được chạy lại trên ontology v12.
- Các quyết định `fix`, `merge` và `split` của Stage B đã được áp dụng.
- Stage C sẽ biên tập từng câu tiếng Việt trên draft này.
- Stage E mới chia family thành `train.jsonl`, `val.jsonl` và `test.jsonl` chính
  thức; không dùng split v1 làm split v2.

Sinh lại các artifact Stage B bằng:

```bash
python -m ontchatbot.cli.apply_stage_b
```
