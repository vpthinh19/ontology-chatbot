# Dataset production

Bộ dữ liệu dạy một model seq2seq sinh truy vấn `SELECT` SPARQL trên một dòng
hoặc marker chính xác `không có thông tin`. Mỗi bản ghi JSON Lines có đúng năm
trường:

```json
{"id":"question-000001","query_id":"procedure-instruction","register":"formal","input":"Xin hướng dẫn thủ tục xin phép nghỉ học.","target":"SELECT ?answer WHERE { :ClassAbsenceRequestProcedure :instructionProvision ?part . ?part :officialText ?answer . }"}
```

- `id`: định danh câu hỏi.
- `query_id`: định danh một họ logic truy vấn trong `catalogue.jsonl`.
- `register`: `formal`, `neutral`, `colloquial` hoặc `noisy`.
- `input`: câu hỏi tiếng Việt tự nhiên.
- `target`: SPARQL canonical không chứa `PREFIX`, hoặc marker từ chối.

Đặc trưng như số cột, graph hop, aggregate, lọc và sắp xếp được suy ra từ
target khi tạo báo cáo; chúng không được nhập tay vào JSONL.

Ba tập có vai trò tách biệt:

| Tập | Câu | Họ truy vấn | Mục đích |
|---|---:|---:|---|
| `train.jsonl` | 340 | 24 | Dạy toàn bộ IRI, dạng SPARQL và nhóm từ chối |
| `val.jsonl` | 58 | 24 | Chọn checkpoint trên cách diễn đạt chưa thấy |
| `test.jsonl` | 58 | 24 | Đánh giá cuối trên cách diễn đạt chưa thấy |

Catalogue có 23 họ trong miền và một họ từ chối. Train chứa mọi giá trị IRI hữu
hạn; validation/test giữ lại cách diễn đạt chứ không giấu schema. Mỗi họ có ít
nhất bốn câu train đủ bốn register và ít nhất hai câu thuộc hai register khác
nhau trong từng tập held-out. Họ truy vấn có slot số có thể tạo nhiều target
khác nhau, nên `query_id` không ánh xạ một-một với chuỗi target.

Trong 456 câu có 96 câu từ chối (21,1%); phần còn lại phủ quy trình, học phí và
thanh toán, biểu mẫu, quy tắc học vụ định lượng và quy đổi chứng chỉ. Không có
câu hỏi đã chuẩn hóa hoặc câu gần trùng cùng họ nằm ở hai tập khác nhau. Mọi
target SPARQL đều parse được, chạy được trên
[`ontology.ttl`](../../ontology/ontology.ttl) và trả ít nhất một dòng literal.

`manifest.json` chứa kích thước, contract chia tập và SHA-256 để kiểm tra tính
toàn vẹn. Có thể xác minh lại bằng:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
