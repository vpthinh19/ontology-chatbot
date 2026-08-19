# Bộ câu hỏi

Tệp này trả lời bộ dữ liệu dùng để dạy và chấm các mô hình gồm những gì.

## Quy mô và cách chia

Bộ câu hỏi có 6.308 dòng. Mỗi dòng ghép một câu hỏi tiếng Việt với đầu ra đúng mà hệ thống cần tạo.

| Tập dữ liệu | Số dòng | Mục đích |
|---|---:|---|
| Tập dạy | 5.518 | Dạy mô hình đổi câu hỏi thành đầu ra có cấu trúc. |
| Tập chỉnh | 400 | Chọn thiết lập trước khi chấm cuối. |
| Tập chấm | 390 | Đo kết quả sau khi đã cố định các lựa chọn. |
| Tổng | 6.308 | Toàn bộ bộ câu hỏi. |

Tập chấm không dùng để chọn mô hình hoặc điều chỉnh cách dạy.

## Hình dạng dữ liệu

| Phần | Ý nghĩa |
|---|---|
| Mã nhận diện | Phân biệt từng câu hỏi. |
| Câu hỏi | Câu tiếng Việt mà người dùng có thể đặt. |
| Loại truy vấn | Mẫu dữ liệu cần lấy. |
| Đầu ra đúng | Một câu SPARQL hoặc “không có thông tin”. |

SPARQL là ngôn ngữ hỏi dữ liệu có cấu trúc. Có 50 khuôn truy vấn. Mỗi khuôn giới hạn kiểu dữ liệu hệ thống được phép đọc.

## Phạm vi nội dung

| Miền câu hỏi | Số câu |
|---|---:|
| Quy tắc học vụ | 1.742 |
| Thủ tục | 1.121 |
| Văn bản | 1.115 |
| Ngoài phạm vi | 884 |
| Biểu mẫu | 634 |
| Chứng chỉ | 476 |
| Học phí | 336 |

Bộ dữ liệu có bốn giọng hỏi: trang trọng, trung tính, thân mật và gõ vội không dấu.

## Kiểm tra dữ liệu

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests/research -q
```

Lệnh đầu kiểm tra bộ dữ liệu có khớp ontology và 50 khuôn truy vấn. Lệnh sau chạy các phép kiểm về dữ liệu và đánh giá.

## Tài liệu liên quan

- [Ontology và nguồn](ONTOLOGY.md)
- [Huấn luyện](TRAINING.md)
- [Cách đo kết quả](EVALUATION.md)
