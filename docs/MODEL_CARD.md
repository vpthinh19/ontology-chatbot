# Thông tin về mô hình

Tệp này trả lời các mô hình dùng để làm gì, phạm vi dữ liệu và cách đọc kết quả.

## Mô hình

Dự án so sánh bốn mô hình chuỗi-chuỗi do bốn tổ chức phát triển. Mỗi mô hình nhận câu hỏi học vụ tiếng Việt và tạo một câu SPARQL hoặc “không có thông tin”. SPARQL là ngôn ngữ hỏi dữ liệu có cấu trúc.

Mô hình không tự viết câu trả lời học vụ cuối cùng. Hệ thống dùng câu truy vấn hợp lệ để lấy dữ kiện và nguồn từ ontology.

## Dữ liệu và kết quả

Bộ dữ liệu có 6.308 dòng, gồm tập dạy, tập chỉnh và tập chấm. Bốn giọng hỏi là trang trọng, trung tính, thân mật và gõ vội không dấu.

Các chỉ số báo cáo là chọn đúng mục trong đồ thị, dựng đúng dạng truy vấn và từ chối đúng câu ngoài phạm vi. Cách chia dữ liệu xem [Bộ câu hỏi](DATASET.md). Định nghĩa chỉ số và kết quả xem [Cách đo kết quả](EVALUATION.md).

## Giới hạn sử dụng

- Không dùng kết quả để suy đoán thông tin không có trong ontology.
- Không dùng kết quả thay thế văn bản chính thức.
- Kiểm tra đường dẫn và trích dẫn nguồn trước khi quyết định về hồ sơ, thời hạn hoặc học phí.

## Tài liệu liên quan

- [Cách các thành phần phối hợp](ARCHITECTURE.md)
- [Đưa vào môi trường sử dụng](DEPLOYMENT.md)
