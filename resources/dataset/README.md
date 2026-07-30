# Dataset

Thư mục này chứa 4.454 câu dùng chung cho huấn luyện và đánh giá chatbot
ontology. Dataset có 3.645 câu train, 402 câu validation, 407 câu test và đủ 51
họ truy vấn của `catalogue.jsonl`.

Mỗi dòng JSONL gồm `id`, `query_id`, `register`, `input`, `target`. Target là một
dòng SPARQL chuẩn hoặc marker chính xác `không có thông tin`. Ba tập chứa
cả câu trong miền lẫn ngoài miền; không có dataset phân loại riêng.

| Tập | Câu | Họ truy vấn |
|---|---:|---:|
| `train.jsonl` | 3.645 | 51 |
| `val.jsonl` | 402 | 51 |
| `test.jsonl` | 407 | 51 |

`manifest.json` lưu cấu trúc, quy tắc chia tập và checksum. `coverage.json` định
nghĩa yêu cầu độ phủ theo miền, phong cách diễn đạt, ca số và bảy nhóm từ chối.
Tập test chỉ phục vụ đánh giá cuối, không dùng để biên soạn thêm câu hoặc chọn
checkpoint.

Riêng miền quy trình có 142 truy vấn đích. Train chứa 2.128 câu
`procedure-*`, mỗi target có ít nhất mười câu và đủ bốn phong cách;
validation/test đều phủ đủ 142 target. Báo cáo chi tiết nằm tại
`reports/procedure-dataset.json`.

Kiểm tra và sinh lại báo cáo bằng:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
