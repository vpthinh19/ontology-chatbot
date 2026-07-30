# Báo cáo tái tạo được

Thư mục này chứa số liệu và hình ảnh được sinh trực tiếp từ dataset 4.454 câu:

- `dataset.json`: kích thước, phân bố, coverage, thống kê ontology và checksum;
- `procedure-dataset.json`: độ phủ 142 target quy trình theo split và checksum;
- `figures/dataset-splits.svg`: số câu train/validation/test;
- `figures/registers.svg`: phân bố bốn phong cách câu hỏi;
- `figures/query-features.svg`: đặc trưng SPARQL theo từng split.
- `models.json`: giao thức, đường học và metric cuối của ba model;
- `figures/training-loss.svg`, `validation-curve.svg`: quá trình fine-tune;
- `figures/model-comparison.svg`: benchmark validation/test;
- `figures/test-by-register.svg`, `test-by-query-feature.svg`: phân rã lỗi.

Sinh lại bằng `uv run generate_reports`. `training_readiness.ready` phải là
`true`, coverage phải hoàn chỉnh và cả 51 họ truy vấn phải có trong ba split.

Bộ 308 câu tại `resources/cases/procedure_language.jsonl` là cổng chấp nhận
production riêng, không phải benchmark khoa học độc lập.

Báo cáo model được sinh từ ba checkpoint đã merge và benchmark trên cùng 402
câu validation, 407 câu test cùng checksum dataset. T5Gemma2 là model triển
khai; kết quả CT2/web được giữ riêng để không trộn backend lượng tử hóa với
benchmark Transformers.
