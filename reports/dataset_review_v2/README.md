# Dataset semantic review v2 — Stage B

Thư mục này ghi kết quả review **target SPARQL và ý nghĩa semantic family** của
dataset v1. Stage B không sửa `sparql_v1`, không viết lại câu tiếng Việt, không
bổ sung coverage và không train model.

Nguồn review được khóa bằng checksum trong `decision_manifest.json`. Mọi target
được thực thi lại trên `ontology_v11.ttl`; kết quả nằm trong
`target_evidence.jsonl`.

## File

- `decision_manifest.json`: quyết định của reviewer, selector có số lượng kỳ
  vọng và lý do; chỉ áp dụng cho đúng worksheet/checksum đã khóa.
- `family_decisions.jsonl`: kết quả mở rộng đủ 401 family, dùng làm đầu vào cho
  các stage biên tập tiếp theo.
- `target_evidence.jsonl`: 80 target cùng bảng kết quả thực tế trên ontology.
- `report.md`: tóm tắt phát hiện và các điểm phải xử lý trước khi đóng băng v2.

`keep` chỉ xác nhận target và nghĩa family hiện khớp. `fix`, `split` và `merge`
là yêu cầu cho draft v2, không phải thay đổi đã được áp dụng vào baseline.

Các family thuộc test v1 có `v2_scope=legacy_test_audit_only`: chúng được kiểm
tra reference nhưng không được sao chép hoặc paraphrase vào train/val v2. Điểm
benchmark/model không được dùng trong quyết định Stage B.
