# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: kích thước, phân bố, contract trong miền, thống kê
  ontology, trạng thái sẵn sàng huấn luyện và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/registers.svg`: phân bố phong cách câu hỏi.
- `figures/query-features.svg`: các đặc trưng SPARQL suy ra theo split.
- `models.json`: metric validation, test, tài nguyên huấn luyện, tốc độ suy
  luận và đường học của ba model.
- `figures/training-loss.svg`: train loss theo epoch.
- `figures/validation-curve.svg`: validation Answer Exact theo epoch.
- `figures/model-comparison.svg`: validation/test Answer Exact và test Result
  F1 của ba model.
- `figures/test-by-register.svg`: test Answer Exact theo phong cách câu hỏi.
- `figures/test-by-query-feature.svg`: test Answer Exact theo đặc trưng SPARQL.

Sinh lại bằng `uv run generate_reports`. Metric model chỉ được tổng hợp khi cả
ba checkpoint hợp lệ trên cùng cách chia dữ liệu và đã được nạp lại độc lập;
không lấy kết quả từ model còn nằm trong RAM của Trainer.
