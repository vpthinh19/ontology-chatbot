# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: kích thước, phân bố, contract trong miền, thống kê
  ontology, trạng thái sẵn sàng huấn luyện và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/registers.svg`: phân bố phong cách câu hỏi.
- `figures/query-features.svg`: các đặc trưng SPARQL suy ra theo split.

Sinh lại bằng `uv run generate_reports`. Báo cáo model hiện chưa có vì chưa
fine-tune trên release chính thức này. Sau huấn luyện, metric chỉ được tổng hợp
khi các checkpoint hợp lệ trên cùng cách chia dữ liệu và đã được nạp lại độc
lập; không lấy kết quả từ model còn nằm trong RAM của Trainer.
