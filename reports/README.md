# Báo cáo tái tạo được

Thư mục này chứa số liệu và hình ảnh được sinh trực tiếp từ dataset 2.150 câu:

- `dataset.json`: kích thước, phân bố, coverage, thống kê ontology và checksum;
- `figures/dataset-splits.svg`: số câu train/validation/test;
- `figures/registers.svg`: phân bố bốn phong cách câu hỏi;
- `figures/query-features.svg`: đặc trưng SPARQL theo từng split.

Sinh lại bằng `uv run generate_reports`. `training_readiness.ready` phải là
`true`, coverage phải hoàn chỉnh và cả 51 họ truy vấn phải có trong ba split.

Chưa có báo cáo benchmark model chính thức trên release này. Báo cáo model chỉ
được tạo sau khi từng checkpoint đã được nạp lại độc lập và đánh giá trên cùng
validation/test cùng checksum dataset.
