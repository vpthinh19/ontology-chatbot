# Model card — trạng thái đã ngừng

## Trạng thái

Model seq2seq từng đi kèm repository đã **ngừng sử dụng**. Nó được dựng trên
dataset hỏng, vì vậy:

- không có metric nào của model được công bố;
- không dùng checkpoint làm baseline;
- không dùng checkpoint làm phương án lui;
- không dùng kết luận chọn model cũ để thiết kế hệ thống.

Tài liệu này cố ý không cung cấp lệnh tải hoặc chạy model cũ.

## Kiến trúc thay thế

V3 không chỉ định một checkpoint chatbot nhỏ. Một LLM lớn ở lớp hội thoại gọi
công cụ ontology, nhận trọn node cùng nguồn rồi tổng hợp câu trả lời. Thành phần
ánh xạ câu hỏi sang SPARQL phải bị giới hạn bởi danh mục truy vấn và được đánh
giá lại trên artifact đồng bộ.

## Dấu vết còn lại

`docs/TRAINING.md` mô tả quy trình huấn luyện lịch sử mà không giữ con số hoặc
kết quả. `artifacts/reports/provenance.json` đánh dấu `model_metrics.status` và
`deployment_metrics.status` là `stale`; đây là cảnh báo vô hiệu, không phải một
mức chất lượng.

Repository hiện chưa có model card định lượng. Chỉ tạo model card mới sau
khi toàn bộ kiểm tra dữ liệu xanh và benchmark mới có artifact máy đọc.
