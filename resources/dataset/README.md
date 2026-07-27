# Dataset

Bộ dữ liệu ánh xạ câu hỏi tiếng Việt sang một truy vấn `SELECT` SPARQL trên
một dòng. Mỗi bản ghi JSON Lines có đúng sáu trường:

```json
{"id":"question-0001","family_id":"family-0001","register":"formal","query_shape":"direct","input":"...","target":"SELECT ..."}
```

- `id`: định danh câu hỏi.
- `family_id`: nhóm bốn câu hỏi có cùng ý nghĩa và cùng target.
- `register`: `formal`, `neutral`, `colloquial` hoặc `noisy`.
- `query_shape`: hình dạng truy vấn dùng để phân tích kết quả.
- `input`: câu hỏi tiếng Việt tự nhiên.
- `target`: SPARQL canonical không chứa phần khai báo `PREFIX`.

Ba tập có vai trò tách biệt:

| Tập | Câu | Họ ngữ nghĩa | Mục đích |
|---|---:|---:|---|
| `train.jsonl` | 1.040 | 260 | Cập nhật trọng số model |
| `val.jsonl` | 140 | 35 | Chọn checkpoint trên các cách diễn đạt chưa thấy |
| `test.jsonl` | 156 | 39 | Đánh giá cuối trên các target ngữ nghĩa chưa thấy |

Validation chỉ chứa các họ câu hỏi chưa có trong train nhưng target chính xác
đã có trong train. Test không trùng target với train; tuy nhiên mọi class,
property và individual cần để tạo truy vấn test đều đã xuất hiện trong train.
Thiết kế này tách khả năng hiểu cách diễn đạt khỏi khả năng ghép một truy vấn
mới bằng các thành phần schema đã học.

Mỗi họ có đủ bốn register. Không có `family_id`, câu hỏi đã chuẩn hóa hoặc câu
gần trùng nằm ở hai tập khác nhau. Mọi target đều parse được, chạy được trên
[`ontology.ttl`](../ontology/ontology.ttl) và trả ít nhất một dòng dữ liệu.

`manifest.json` chứa kích thước, contract chia tập và SHA-256 để kiểm tra tính
toàn vẹn. Có thể xác minh lại bằng:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
