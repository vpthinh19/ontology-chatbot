# Thông tin về mô hình

Tệp này trả lời mô hình trong dự án dùng để làm gì, dữ liệu nào dùng để dạy và kết quả nào cần xem. Tệp dành cho người đánh giá mô hình mà không cần mở mã nguồn.

## Mục đích sử dụng

Mô hình nhận một câu hỏi học vụ tiếng Việt và tạo một câu SPARQL hoặc “không có thông tin”. SPARQL là ngôn ngữ dùng để hỏi dữ liệu có cấu trúc. Mô hình không tự viết câu trả lời học vụ cuối cùng.

Ontology là tập dữ kiện và liên kết giúp máy tra cứu. Một node là một mục trong ontology, ví dụ một thủ tục, quy định hoặc bảng. Sau khi mô hình chọn được cách hỏi phù hợp, hệ thống lấy dữ kiện của node và nguồn của chúng.

## Dữ liệu dạy và chấm

| Phần dữ liệu | Số dòng | Vai trò |
|---|---:|---|
| Tập dạy | 5.518 | Dạy mô hình đổi câu hỏi thành đầu ra có cấu trúc. |
| Tập chỉnh | 400 | Chọn thiết lập trước khi chấm cuối. |
| Tập chấm | 390 | Đo kết quả cuối. |

Bộ dữ liệu gồm 6.308 dòng và có bốn giọng hỏi: trang trọng, trung tính, thân mật và gõ vội không dấu.

## Kết quả báo cáo

| Chỉ số | Tập chỉnh | Tập chấm |
|---|---:|---:|
| Chọn đúng mục trong đồ thị | 80,2% | 76,4% |
| Dựng đúng dạng truy vấn | 85,5% | 81,8% |
| Từ chối đúng câu ngoài phạm vi | 96,5% | 90,8% |

Các chỉ số này đo việc tạo và kiểm tra truy vấn, không đo chất lượng của câu trả lời hội thoại do một hệ thống khác có thể tạo từ dữ kiện trả về.

## Giới hạn sử dụng

- Không dùng mô hình để suy đoán thông tin không có trong ontology.
- Không dùng kết quả làm căn cứ thay thế văn bản chính thức.
- Cần kiểm tra đường dẫn và trích dẫn nguồn khi câu trả lời ảnh hưởng đến hồ sơ, thời hạn hoặc học phí.
- Câu hỏi gõ vội không dấu là dạng khó hơn các cách diễn đạt còn lại.

## Tài liệu liên quan

- [Bộ câu hỏi](DATASET.md)
- [Cách đo kết quả](EVALUATION.md)
- [Đưa vào môi trường sử dụng](DEPLOYMENT.md)
