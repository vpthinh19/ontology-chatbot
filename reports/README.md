# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: kích thước, phân bố, contract tổng quát hóa, thống kê
  ontology, trạng thái sẵn sàng huấn luyện và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/registers.svg`: phân bố phong cách câu hỏi.
- `figures/query-features.svg`: các đặc trưng SPARQL suy ra theo split.

Sinh lại bằng `uv run generate_reports`. Báo cáo huấn luyện và benchmark chỉ
được công bố sau khi cả ba model chạy trên dataset canonical hiện tại; metric
của dữ liệu cũ không được trộn vào báo cáo này.
