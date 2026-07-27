# Đánh giá

## Metric

Mỗi prediction được xử lý theo bốn lớp:

| Metric | Cách tính | Ý nghĩa |
|---|---|---|
| Parse rate | Query qua RDFLib parser | Đúng cú pháp |
| Execution rate | Query chạy không lỗi | Có thể thực thi |
| Answer exact | Multiset literal trả về trùng reference | Trả đúng dữ liệu |
| Canonical query exact | Chuỗi query trùng target | Sinh đúng biểu diễn chuẩn |

Answer exact là metric chính. Nó bỏ qua thứ tự dòng và tên biến SPARQL tùy ý,
nhưng vẫn so kiểu dữ liệu, giá trị, số cột và cách các giá trị được nhóm trong
từng dòng. Một query khác chuỗi nhưng trả đúng dữ liệu vẫn được tính đúng.

Metric được báo cáo tổng thể, theo register và theo query shape. Lỗi được chia
thành parse, execution, sai IRI, sai property, thiếu/thừa nhánh, sai literal và
sai ngữ nghĩa còn lại.

## Train, validation và test

- Train loss được vẽ theo bước để nhận biết hội tụ hoặc bất ổn.
- Validation answer exact được vẽ theo checkpoint và dùng để chọn model.
- Test chỉ chạy với checkpoint đã chọn và là số dùng so sánh ba model.

Vì validation và test có mục tiêu khác nhau, không gộp hai con số thành một tỷ
lệ chung. Điểm test phải luôn đi kèm số câu (156), phân bố register và query
shape.

## Biểu đồ công khai

`generate_reports` sinh biểu đồ dataset. Sau huấn luyện, báo cáo model bổ sung:

- đường train loss và validation answer exact;
- cột so sánh model trên test;
- breakdown theo phong cách câu hỏi và hình dạng query;
- thời gian train, VRAM đỉnh và tốc độ inference.

Các JSON gốc được giữ cạnh SVG để người đọc kiểm tra con số mà không cần mở
code trainer.
