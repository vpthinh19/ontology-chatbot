# Báo cáo tái tạo được

Thư mục này chứa số liệu và hình ảnh được sinh trực tiếp từ dataset 4.454 câu:

- `dataset.json`: kích thước, phân bố, độ phủ, thống kê ontology và checksum;
- `procedure-dataset.json`: độ phủ 142 target quy trình theo split và checksum;
- `figures/dataset-splits.svg`: số câu train/validation/test;
- `figures/registers.svg`: phân bố bốn phong cách câu hỏi;
- `figures/query-features.svg`: đặc trưng SPARQL theo từng split.
- `models.json`: giao thức, đường học và metric cuối của ba model;
- `provenance.json`: fingerprint baseline v0.4.1, fingerprint input canonical
  hiện hành và trạng thái metric model/triển khai;
- `figures/training-loss.svg`, `validation-curve.svg`: quá trình fine-tune;
- `figures/model-comparison.svg`: benchmark validation/test;
- `figures/test-by-register.svg`, `test-by-query-feature.svg`: phân rã lỗi.

`ontology.ttl`, `catalogue.jsonl`, `coverage.json` và ba split là input
canonical. Inventory, manifest, `dataset.json`, `procedure-dataset.json`,
`provenance.json` và ba biểu đồ dataset là artifact dẫn xuất. Kiểm tra read-only
bằng `uv run validate_sparql_dataset`; sinh lại artifact bằng
`uv run generate_reports`. `training_readiness.ready` phải là `true`, yêu cầu
độ phủ phải được đáp ứng và cả 51 họ truy vấn phải có trong ba tập.

Bộ 308 câu tại `resources/cases/procedure_language.jsonl` kiểm tra hồi quy cho
hành vi triển khai, không phải benchmark khoa học độc lập.

Báo cáo model được sinh từ ba checkpoint đã merge và benchmark trên cùng 402
câu validation, 407 câu test cùng checksum dataset. T5Gemma2 là model triển
khai; kết quả CT2/web được giữ riêng để không trộn backend lượng tử hóa với
benchmark Transformers.

Các số liệu model và CT2/web hiện có là baseline v0.4.1. Nếu một input canonical
thay đổi mà chưa benchmark lại, generator giữ nguyên các số liệu lịch sử và đặt
trạng thái tương ứng trong `reports/provenance.json` thành `stale`.
