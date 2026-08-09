# Dataset

> **Đang được xây dựng lại.** Ba tệp `train.jsonl`, `val.jsonl`, `test.jsonl`
> được tạo trước đợt tái cấu trúc ontology và **không còn hợp lệ**: các truy vấn
> đích của chúng dùng những quan hệ đã bị thay thế. Chúng được giữ lại để đối
> chiếu cho tới khi bộ mới được sinh xong.

## Các tệp

| Tệp | Vai trò | Trạng thái |
|---|---|---|
| `catalogue.jsonl` | 183 họ truy vấn model được phép sinh, trong đó 63 họ primary | hợp lệ |
| `catalogue-manual.jsonl` | 29 họ viết tay, được trộn vào khi dựng lại danh mục | hợp lệ |
| `coverage.json` | yêu cầu độ phủ theo miền, phong cách, ca số và tám nhóm từ chối | hợp lệ |
| `manifest.json` | cấu trúc, quy tắc chia tập và checksum | dẫn xuất, sinh cùng dataset |
| `train.jsonl` `val.jsonl` `test.jsonl` | 5.204 / 349 / 349 câu | hợp lệ |

## Danh mục truy vấn

`catalogue.jsonl` là hợp đồng ràng buộc chứ không phải tài liệu tham khảo:
backend chỉ thực thi truy vấn khớp chính xác một họ đã khai ở đây.

| Miền | Số họ |
|---|---:|
| Quy tắc học vụ | 64 |
| Học phí | 32 |
| Quy trình học vụ | 24 |
| Tra cứu văn bản | 23 |
| Chứng chỉ | 23 |
| Biểu mẫu | 15 |
| Giới thiệu năng lực | 1 |
| Từ chối trả lời | 1 |

Mỗi họ mang một tầng: **63 họ primary** bắt buộc có dữ liệu huấn luyện, **120 họ
secondary** vẫn truy vấn được ở runtime nhưng không tiêu ngân sách dạy học. Phần
lớn họ secondary là câu hỏi vòng tròn không ai đặt ("khoản 3 Điều 24 thuộc điều số
mấy"); số còn lại là những họ **cố ý bị hạ** vì trùng ý với một họ khác — ép model
chọn giữa hai đích đều đúng chỉ dạy nó đoán bừa.

153 họ được sinh tự động từ ontology. 29 họ trong `catalogue-manual.jsonl` phải
viết tay vì cần so sánh ngưỡng ("7,5 điểm xếp loại gì", "70 tín chỉ là năm mấy",
"học phí ngành X khoá 65"), gom nhiều cột về một bản ghi, hoặc trả nội dung kèm
nguồn trích dẫn và link văn bản gốc — bộ sinh cơ học chỉ dựng được truy vấn đi
theo một đường dẫn. Dựng lại danh mục bằng:

```bash
uv run python -m ontchatbot.research.build_catalogue
```

## Hình dạng một bản ghi

Mỗi dòng JSONL gồm `id`, `query_id`, `register`, `input`, `target`. Target là một
dòng SPARQL chuẩn hoặc marker chính xác `không có thông tin`. Ba tập chứa cả câu
trong miền lẫn ngoài miền; không có dataset phân loại riêng. Tập test chỉ phục vụ
đánh giá cuối, không dùng để biên soạn thêm câu hoặc chọn checkpoint.

## Kiểm tra

```bash
uv run validate_sparql_dataset
uv run generate_reports
```
