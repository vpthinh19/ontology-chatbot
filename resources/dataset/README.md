# Dataset

Bộ dữ liệu ánh xạ câu hỏi tiếng Việt sang một truy vấn `SELECT` SPARQL trên
một dòng. Mỗi bản ghi JSON Lines có đúng năm trường:

```json
{"id":"question-0001","query_id":"query-0001","register":"formal","input":"...","target":"SELECT ..."}
```

- `id`: định danh câu hỏi.
- `query_id`: định danh một query canonical, ánh xạ một-một với target.
- `register`: `formal`, `neutral`, `colloquial` hoặc `noisy`.
- `input`: câu hỏi tiếng Việt tự nhiên.
- `target`: SPARQL canonical không chứa phần khai báo `PREFIX`.

Đặc trưng như số cột, graph hop, aggregate, lọc và sắp xếp được suy ra từ
target khi tạo báo cáo; chúng không được nhập tay vào JSONL.

Ba tập có vai trò tách biệt:

| Tập | Câu | Query | Mục đích |
|---|---:|---:|---|
| `train.jsonl` | 1.150 | 215 | Dạy toàn bộ query được hỗ trợ |
| `val.jsonl` | 215 | 215 | Chọn checkpoint trên cách diễn đạt chưa thấy |
| `test.jsonl` | 215 | 215 | Đánh giá cuối trên cách diễn đạt chưa thấy |

Mỗi query có đúng một câu validation, một câu test và ít nhất hai câu train.
Validation và test giữ lại cách diễn đạt, không giữ lại logic query. Thiết kế
này đánh giá chatbot trong danh mục chức năng đã công bố; nó không tuyên bố khả
năng zero-shot với query hoặc ontology chưa biết.

Register được cân bằng trong từng split. Không có câu hỏi đã chuẩn hóa hoặc câu
gần trùng nằm ở hai tập khác nhau. Mọi target đều parse được, chạy được trên
[`ontology.ttl`](../ontology/ontology.ttl) và trả ít nhất một dòng dữ liệu.

`manifest.json` chứa kích thước, contract chia tập và SHA-256 để kiểm tra tính
toàn vẹn. Có thể xác minh lại bằng:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
