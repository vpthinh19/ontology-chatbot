# Dataset review v2 — Stage B đến G

Trạng thái hiện tại: **Stage B–G đã hoàn tất trên ontology v12; release v2 đã
đóng băng và nghiệm thu bằng model**. Đọc `stage_g_report.md` để xem kết quả
mới nhất. `report.md`,
`family_decisions.jsonl` và `target_evidence.jsonl` là bằng chứng của lượt
review ban đầu trên v11, được giữ nguyên để tái lập lịch sử.

Thư mục này ghi kết quả review **target SPARQL và ý nghĩa semantic family** của
dataset v1. Baseline `sparql_v1` không bị sửa. Lượt review ban đầu không viết
lại câu tiếng Việt; bước hoàn tất chỉ áp dụng các sửa đổi đã duyệt vào draft
v2, không bổ sung coverage và không train model.

Nguồn review được khóa bằng checksum trong `decision_manifest.json`. Mọi target
của lượt review ban đầu được thực thi trên `ontology_v11.ttl`; kết quả lịch sử
nằm trong `target_evidence.jsonl`. Target của draft v2 sau sửa được thực thi
lại trên v12 trong `target_evidence_v12.jsonl`.

## File

- `decision_manifest.json`: quyết định của reviewer, selector có số lượng kỳ
  vọng và lý do; chỉ áp dụng cho đúng worksheet/checksum đã khóa.
- `family_decisions.jsonl`: kết quả mở rộng đủ 401 family, dùng làm đầu vào cho
  các stage biên tập tiếp theo.
- `target_evidence.jsonl`: 80 target cùng bảng kết quả thực tế trên ontology.
- `report.md`: tóm tắt phát hiện và các điểm phải xử lý trước khi đóng băng v2.
- `completion_manifest.json`: checksum và số liệu draft đã áp dụng quyết định.
- `target_evidence_v12.jsonl`: kết quả thật của target sau sửa trên v12.
- `completion_report.md`: báo cáo ngắn xác nhận Stage B hoàn tất.
- `stage_c_decisions.json`, `stage_c_audit.json` và `stage_c_report.md`: quyết
  định cùng kết quả review ngôn ngữ của 948 input.
- `stage_d_decisions.json`: các lỗ hổng được `add`, `complete`, `defer` hoặc
  xác nhận `not_gap`, luôn kèm lý do review.
- `stage_d_coverage.json`: ma trận coverage trước và sau Stage D.
- `stage_d_audit.json`, `target_evidence_stage_d.jsonl` và
  `stage_d_report.md`: cổng chất lượng, kết quả thực thi 102 target và báo cáo
  hoàn tất coverage draft.
- `stage_e_audit.json` và `stage_e_report.md`: bằng chứng chia đủ 234 family,
  compositional holdout, kiểm tra leakage và chính sách khóa test v2.
- `stage_e_manifest.json`: ảnh chụp manifest candidate trước khi đóng băng.
- `stage_f_audit.json` và `stage_f_report.md`: bằng chứng release gate cấu
  trúc/tokenizer và checksum manifest v2 đã đóng băng.
- `stage_g_protocol.json`: cấu hình, môi trường và ba checkpoint seed 42 được khóa
  trước khi test được mở.
- `stage_g_audit.json` và `stage_g_report.md`: kết quả 3 model × 1 seed, phân
  tích target mới, nhóm lỗi bền vững và kết luận chất lượng v2.

`keep` chỉ xác nhận target và nghĩa family hiện khớp. `fix`, `split` và `merge`
là yêu cầu cho draft v2, không phải thay đổi đã được áp dụng vào baseline.

Các family thuộc test v1 có `v2_scope=legacy_test_audit_only`: chúng được kiểm
tra reference nhưng không được sao chép hoặc paraphrase vào train/val v2. Điểm
benchmark/model không được dùng trong quyết định Stage B.
