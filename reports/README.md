# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: kích thước, phân bố, contract trong miền, thống kê
  ontology, trạng thái sẵn sàng huấn luyện và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/registers.svg`: phân bố phong cách câu hỏi.
- `figures/query-features.svg`: các đặc trưng SPARQL suy ra theo split.

Sinh lại bằng `uv run generate_reports`. Thư mục chỉ công bố số liệu dataset và
ontology cho tới khi cả ba model có checkpoint hợp lệ trên cùng cách chia dữ
liệu. Khi đó metric phải được lấy từ checkpoint đã lưu và nạp lại độc lập,
không lấy từ model còn nằm trong RAM của Trainer.
