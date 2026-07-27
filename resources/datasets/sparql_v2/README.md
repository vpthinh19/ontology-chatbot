# Dataset SPARQL v2 — working draft

`draft.jsonl` là đầu vào đã hoàn tất semantic review Stage B.
`language_draft.jsonl` là đầu ra đã hoàn tất review ngôn ngữ Stage C. Cả hai
đều là artifact làm việc, chưa phải release train/val/test cuối cùng.

- Nguồn chỉ gồm train và validation của v1.
- Test v1 là audit-only và không được sao chép vào draft.
- Target đã được chạy lại trên ontology v12.
- Các quyết định `fix`, `merge` và `split` của Stage B đã được áp dụng.
- Stage C đã đọc toàn bộ 948 input, giữ 865 record chất lượng hơn trong
  `language_draft.jsonl`.
- Stage E mới chia family thành `train.jsonl`, `val.jsonl` và `test.jsonl` chính
  thức; không dùng split v1 làm split v2.

Sinh lại các artifact Stage B bằng:

```bash
python -m ontchatbot.cli.apply_stage_b
python -m ontchatbot.cli.apply_stage_c
```
