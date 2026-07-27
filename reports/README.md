# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: kích thước, phân bố, contract tổng quát hóa, thống kê
  ontology, trạng thái sẵn sàng huấn luyện và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/registers.svg`: phân bố phong cách câu hỏi.
- `figures/query-features.svg`: các đặc trưng SPARQL suy ra theo split.
- `models.json`: giao thức, metric tổng thể, phân rã lỗi và đường học của ba
  artifact đã nạp lại độc lập.
- `figures/model-comparison.svg`: validation answer exact, test answer exact và
  test result F1.
- `figures/training-loss.svg`, `figures/validation-curve.svg`: quá trình học.
- `figures/test-by-register.svg`, `figures/test-by-query-feature.svg`: answer
  exact trên từng nhóm test.

Sinh lại bằng `uv run generate_reports`. Metric model được lấy từ checkpoint
đã lưu và nạp lại qua `from_pretrained()`, không lấy từ model còn nằm trong RAM
của Trainer. Metric của dữ liệu cũ không được trộn vào báo cáo này.
