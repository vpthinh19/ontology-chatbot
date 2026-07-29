# Dataset hợp nhất

Thư mục này chứa 2.888 câu dùng chung cho huấn luyện và đánh giá chatbot
ontology. Dataset có 2.079 câu train, 402 câu validation, 407 câu test và đủ 51
họ truy vấn của `catalogue.jsonl`.

Mỗi dòng JSONL gồm `id`, `query_id`, `register`, `input`, `target`. Target là một
dòng SPARQL canonical hoặc marker chính xác `không có thông tin`. Ba split chứa
cả câu trong miền lẫn ngoài miền; không có dataset phân loại riêng.

| Tập | Câu | Họ truy vấn |
|---|---:|---:|
| `train.jsonl` | 2.079 | 51 |
| `val.jsonl` | 402 | 51 |
| `test.jsonl` | 407 | 51 |

`manifest.json` lưu contract và checksum. `coverage.json` định nghĩa yêu cầu độ
phủ theo miền, register, ca số và bảy nhóm từ chối. Test đã đóng băng; không dùng
test để biên soạn thêm câu hoặc chọn checkpoint.

Riêng miền quy trình có 142 target canonical. Train chứa 962 câu `procedure-*`,
mỗi target có ít nhất sáu câu và đủ bốn phong cách; validation/test đều phủ đủ
142 target. Báo cáo chi tiết nằm tại `reports/procedure-dataset.json`.

Kiểm tra và sinh lại báo cáo bằng:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
