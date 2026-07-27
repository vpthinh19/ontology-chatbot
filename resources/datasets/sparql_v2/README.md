# Dataset SPARQL v2 — Stage E release candidate

`draft.jsonl` là đầu vào đã hoàn tất semantic review Stage B.
`language_draft.jsonl` là đầu ra đã hoàn tất review ngôn ngữ Stage C.
`coverage_draft.jsonl` là đầu ra đã hoàn tất bổ sung coverage Stage D. Ba file
này là lịch sử làm việc có thể tái lập; `train.jsonl`, `val.jsonl` và
`test.jsonl` là release candidate do Stage E sinh ra.

- Nguồn chỉ gồm train và validation của v1.
- Test v1 là audit-only và không được sao chép vào draft.
- Target đã được chạy lại trên ontology v12.
- Các quyết định `fix`, `merge` và `split` của Stage B đã được áp dụng.
- Stage C đã đọc toàn bộ 948 input, giữ 865 record chất lượng hơn trong
  `language_draft.jsonl`.
- Stage D đã bổ sung có review thành 936 record, 234 family và 102 target trong
  `coverage_draft.jsonl`; mọi family có đủ bốn register.
- Stage E chia nguyên vẹn 234 family thành 164 train, 35 validation và 35 test;
  không dùng split v1 làm split v2 và không sao chép record test v1.
- Mỗi split có đủ năm query shape. Validation/test mỗi tập có năm
  compositional holdout đã biết toàn bộ schema nhưng chưa thấy nguyên target.
- `manifest.json` đang ở trạng thái `stage_e_candidate`; Stage F mới đóng băng
  release sau khi chạy đủ cổng kiểm định.
- Không dùng test v2 để sửa dữ liệu, chọn model/checkpoint hoặc tuning.

Sinh lại toàn bộ artifact Stage B–E bằng:

```bash
python -m ontchatbot.cli.apply_stage_b
python -m ontchatbot.cli.apply_stage_c
python -m ontchatbot.cli.apply_stage_d
python -m ontchatbot.cli.apply_stage_e
```
