# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: snapshot candidate pool, gồm kích thước, phân bố, contract
  trong miền, thống kê ontology và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/registers.svg`: phân bố phong cách câu hỏi.
- `figures/query-features.svg`: các đặc trưng SPARQL suy ra theo split.

Sinh lại bằng `uv run generate_reports`. Trường `training_readiness.ready` hiện
chỉ có nghĩa candidate vượt các kiểm tra tĩnh nội bộ của catalogue hiện có; nó
không chứng minh catalogue phủ ontology và không cho phép full fine-tuning.
Báo cáo này sẽ được thay sau khi reporting contract nhận inventory coverage.

Báo cáo model chính thức hiện chưa có. Sau khi dataset được nghiệm thu, metric
chỉ được tổng hợp khi các checkpoint hợp lệ trên cùng cách chia dữ liệu và đã
được nạp lại độc lập; không lấy kết quả từ model còn nằm trong RAM của Trainer.
