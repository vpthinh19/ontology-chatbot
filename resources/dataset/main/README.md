# Dataset hợp nhất

Thư mục này chứa release 2.150 câu dùng chung cho huấn luyện và đánh giá chatbot
ontology. Dataset có 1.550 câu train, 300 câu validation, 300 câu test và đủ 51
họ truy vấn của `catalogue.jsonl`.

Mỗi dòng JSONL gồm `id`, `query_id`, `register`, `input`, `target`. Target là một
dòng SPARQL canonical hoặc marker chính xác `không có thông tin`. Ba split chứa
cả câu trong miền lẫn ngoài miền; không có dataset phân loại riêng.

| Tập | Câu | Họ truy vấn |
|---|---:|---:|
| `train.jsonl` | 1.550 | 51 |
| `val.jsonl` | 300 | 51 |
| `test.jsonl` | 300 | 51 |

`manifest.json` lưu contract và checksum. `coverage.json` định nghĩa yêu cầu độ
phủ theo miền, register, ca số và bảy nhóm từ chối. Test đã đóng băng; không dùng
test để biên soạn thêm câu hoặc chọn checkpoint.

Kiểm tra và sinh lại báo cáo bằng:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
