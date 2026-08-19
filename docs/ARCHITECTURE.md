# Kiến trúc hệ thống

Tệp này trả lời hệ thống biến một câu hỏi học vụ thành dữ kiện có nguồn như thế nào.

## Luồng xử lý

```mermaid
flowchart LR
    A[Câu hỏi tiếng Việt] --> B[Mô hình tạo câu truy vấn]
    B --> C[Kiểm tra khuôn và quyền đọc]
    C -->|Hợp lệ| D[Ontology]
    C -->|Không hợp lệ hoặc ngoài phạm vi| E[Không có thông tin]
    D --> F[Dữ kiện và nguồn]
```

1. Mô hình đổi câu hỏi thành SPARQL.
2. SPARQL là ngôn ngữ hỏi dữ liệu có cấu trúc.
3. Hệ thống chỉ nhận câu truy vấn thuộc một trong 50 khuôn và chỉ đọc dữ liệu.
4. Câu hợp lệ được chạy trên ontology.
5. Kết quả gồm dữ kiện, trích dẫn và đường dẫn tới văn bản gốc.

Ontology là tập dữ kiện học vụ và liên kết về nguồn. Xem [Ontology và nguồn](ONTOLOGY.md) để biết nội dung và nguồn dữ liệu.

## Trách nhiệm của các thành phần

| Thành phần | Trách nhiệm | Không làm |
|---|---|---|
| Bốn mô hình chuỗi-chuỗi | Đổi câu hỏi thành câu truy vấn. | Tự suy đoán quy định. |
| Danh mục khuôn truy vấn | Giới hạn các cách đọc dữ liệu được phép. | Mở quyền truy vấn tuỳ ý. |
| Ontology | Lưu dữ kiện và liên kết về nguồn. | Tự cập nhật quy định. |
| Bộ trả kết quả | Trả dữ kiện có nguồn. | Viết câu trả lời hội thoại. |
| Lớp hội thoại bên ngoài | Gọi công cụ và diễn đạt từ dữ kiện nhận được. | Thay thế dữ kiện có nguồn. |

## Kết quả và lỗi

| Tình huống | Kết quả |
|---|---|
| Tra cứu hợp lệ có dữ liệu | Dữ kiện, trích dẫn và đường dẫn nguồn. |
| Câu hỏi ngoài phạm vi hoặc truy vấn không thuộc khuôn | “Không có thông tin”. |
| Lỗi nạp dữ liệu hoặc lỗi dịch vụ | Lỗi hệ thống. |

Lỗi hệ thống không có nghĩa là thiếu thông tin.

## Tài liệu liên quan

- [Khái niệm và phạm vi](CONCEPT.md)
- [Đưa vào môi trường sử dụng](DEPLOYMENT.md)
