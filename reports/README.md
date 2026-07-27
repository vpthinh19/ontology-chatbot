# Reports

Thư mục này chứa số liệu và hình ảnh dành cho người đọc project:

- `dataset.json`: kích thước, phân bố, contract tổng quát hóa, thống kê
  ontology và checksum.
- `figures/dataset-splits.svg`: số câu train/validation/test.
- `figures/query-shapes.svg`: phân bố hình dạng truy vấn theo split.

Sinh lại bằng `uv run generate_reports`. Báo cáo huấn luyện và benchmark chỉ
được công bố sau khi cả ba model chạy trên dataset canonical hiện tại; metric
của dữ liệu cũ không được trộn vào báo cáo này.
