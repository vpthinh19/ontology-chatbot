# Khái niệm và phạm vi

Tệp này trả lời dự án giải quyết vấn đề gì, tin vào dữ liệu nào và từ chối điều gì. Tệp dành cho người mới cần hiểu phạm vi trước khi dùng hoặc đánh giá hệ thống.

## Mục đích

Dự án giúp tra cứu thông tin học vụ có nguồn từ câu hỏi tiếng Việt. Nó không thay người phụ trách học vụ ra quyết định và không dùng trí nhớ của mô hình để bổ sung quy định không có trong nguồn.

Một ontology là tập dữ kiện cùng các liên kết giữa chúng, được tổ chức để máy có thể tra cứu. Trong dự án, ontology liên kết quy định, thủ tục, biểu mẫu, bảng và các văn bản làm căn cứ.

## Hệ thống trả về gì

| Câu hỏi | Kết quả của công cụ |
|---|---|
| Thuộc dữ liệu dự án | Dữ kiện liên quan, trích dẫn và đường dẫn tới văn bản gốc. |
| Ngoài dữ liệu dự án | “Không có thông tin”. |
| Không xác định được cách tra cứu an toàn | “Không có thông tin”. |
| Dịch vụ gặp lỗi | Lỗi hệ thống để nơi gọi xử lý riêng. |

SPARQL là ngôn ngữ dùng để hỏi ontology. Người dùng chỉ đặt câu hỏi thông thường; mô hình tạo SPARQL ở bên trong và hệ thống chỉ chạy câu khớp khuôn đã cho phép.

## Đơn vị thông tin

Một node là một mục dữ liệu trong ontology. Ví dụ, một node có thể là thủ tục bảo lưu, một điều của quy chế hoặc một bảng trong phụ lục.

Hệ thống ưu tiên lấy đủ dữ kiện và nguồn của node đã chọn. Cách này giúp câu trả lời có cả điều kiện, hồ sơ, nơi nộp hoặc ngoại lệ khi chúng có trong cùng mục dữ liệu.

| Loại nội dung | Cách lưu và trả về |
|---|---|
| Quy định, thủ tục, biểu mẫu | Dữ kiện của mục và liên kết tới phần nguồn. |
| Bảng | Toàn bộ bảng được giữ nguyên dạng để bảo toàn hàng và cột. |
| Thông tin không có trong nguồn | Không suy ra hoặc điền thêm. |

## Ranh giới trách nhiệm

| Thành phần | Trách nhiệm |
|---|---|
| Công cụ của dự án | Chọn dữ kiện có nguồn và trả kết quả tra cứu. |
| Mô hình ngôn ngữ lớn nếu được tích hợp bên ngoài | Hiểu hội thoại và diễn đạt câu trả lời từ kết quả tra cứu. |
| Người dùng hoặc đơn vị phụ trách | Kiểm tra văn bản gốc khi cần quyết định có ảnh hưởng thực tế. |

## Giới hạn nội dung

- Mức học phí của từng người không nằm trong dữ liệu vì phụ thuộc thông tin đăng ký thực tế.
- Phần mơ hồ, thiếu hoặc hỏng trong văn bản nguồn không được tự suy diễn.
- Dữ liệu không tự xác định hiệu lực theo mọi thời điểm của văn bản.

## Tài liệu liên quan

- [Cách các thành phần phối hợp](ARCHITECTURE.md)
- [Ontology và nguồn](ONTOLOGY.md)
- [Bộ câu hỏi](DATASET.md)
- [Cách đo kết quả](EVALUATION.md)
