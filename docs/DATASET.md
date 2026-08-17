# Bộ câu hỏi

Tệp này trả lời bộ dữ liệu dùng để dạy và chấm mô hình gồm những gì. Tệp dành cho người cần đánh giá phạm vi dữ liệu hoặc chạy lại việc huấn luyện mà không đọc mã nguồn.

## Quy mô và cách chia

Bộ câu hỏi có 6.308 dòng. Mỗi dòng ghép một câu hỏi tiếng Việt với đầu ra đúng mà hệ thống cần tạo.

| Tập dữ liệu | Số dòng | Mục đích |
|---|---:|---|
| Tập dạy | 5.518 | Cho mô hình học cách đổi câu hỏi thành đầu ra có cấu trúc. |
| Tập chỉnh | 400 | Chọn thiết lập trước khi chấm cuối cùng. |
| Tập chấm | 390 | Đo kết quả sau khi đã cố định các lựa chọn. |
| Tổng | 6.308 | Toàn bộ bộ câu hỏi. |

Tập chỉnh là phần dữ liệu dùng để lựa chọn cách huấn luyện. Tập chấm được giữ riêng để kết quả cuối không bị ảnh hưởng bởi các lựa chọn đó.

## Hình dạng của một dòng dữ liệu

| Phần | Ý nghĩa |
|---|---|
| Mã nhận diện | Giúp phân biệt từng câu hỏi. |
| Câu hỏi | Câu tiếng Việt mà người dùng có thể đặt. |
| Loại truy vấn | Cho biết mẫu dữ liệu mà câu hỏi cần lấy. |
| Đầu ra đúng | Một câu SPARQL hoặc “không có thông tin”. |

SPARQL là ngôn ngữ dùng để hỏi dữ liệu có cấu trúc trong ontology. Ontology là tập các mục dữ liệu học vụ và liên kết giữa chúng; người học không phải viết SPARQL.

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

Có 50 khuôn truy vấn. Mỗi khuôn giới hạn kiểu dữ liệu mà hệ thống được phép đọc, nên một câu hỏi không thể biến thành yêu cầu truy xuất tùy ý.

Bộ dữ liệu có bốn giọng hỏi: trang trọng, trung tính, thân mật và gõ vội không dấu. Giọng hỏi là cách diễn đạt khác nhau của cùng một nhu cầu thông tin.

## Điều bộ dữ liệu không làm

- Không là nguồn quy định học vụ; nguồn là các văn bản được liên kết trong ontology.
- Không thay thế câu trả lời cuối cho người dùng.
- Không dùng tập chấm để chọn mô hình hoặc điều chỉnh cách dạy.

## Kiểm tra dữ liệu

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests/research -q
```

Lệnh đầu kiểm tra bộ dữ liệu có khớp ontology và 50 khuôn truy vấn hay không. Lệnh sau chạy các phép kiểm tự động liên quan đến dữ liệu và đánh giá.

## Tài liệu liên quan

- [Ontology và nguồn](ONTOLOGY.md)
- [Huấn luyện](TRAINING.md)
- [Cách đo kết quả](EVALUATION.md)
