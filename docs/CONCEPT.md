# Khái niệm và phạm vi

Tệp này trả lời dự án giải quyết vấn đề gì và từ chối điều gì.

## Mục đích

Dự án tra cứu thông tin học vụ có nguồn từ câu hỏi tiếng Việt. Nó không thay đơn vị phụ trách ra quyết định. Nó không dùng trí nhớ của mô hình để bổ sung quy định không có trong nguồn.

## Phạm vi kết quả

| Câu hỏi | Kết quả của công cụ |
|---|---|
| Thuộc dữ liệu dự án | Dữ kiện, trích dẫn và đường dẫn tới văn bản gốc. |
| Ngoài dữ liệu hoặc không xác định được cách tra cứu an toàn | “Không có thông tin”. |
| Dịch vụ gặp lỗi | Lỗi hệ thống để nơi gọi xử lý. |

## Ranh giới trách nhiệm

| Thành phần | Trách nhiệm |
|---|---|
| Công cụ của dự án | Chọn dữ kiện có nguồn và trả kết quả tra cứu. |
| Mô hình ngôn ngữ lớn tích hợp bên ngoài | Hiểu hội thoại và diễn đạt từ kết quả tra cứu. |
| Người dùng hoặc đơn vị phụ trách | Kiểm tra văn bản gốc khi quyết định có ảnh hưởng thực tế. |

## Giới hạn nội dung

- Học phí của từng người không nằm trong dữ liệu vì phụ thuộc đăng ký thực tế.
- Phần mơ hồ, thiếu hoặc hỏng trong nguồn không được suy diễn.
- Dữ liệu không tự xác định hiệu lực của mọi văn bản ở mọi thời điểm.

Khái niệm ontology, nguồn và đơn vị dữ liệu được giải thích trong [Ontology và nguồn](ONTOLOGY.md).

## Tài liệu liên quan

- [Cách các thành phần phối hợp](ARCHITECTURE.md)
- [Bộ câu hỏi](DATASET.md)
