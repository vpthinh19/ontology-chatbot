# Ý tưởng hệ thống và ranh giới trả lời

## Vai trò của chatbot

Chatbot ontology không còn là model nhỏ tự nhận câu hỏi rồi trả lời trực tiếp.
Nó là **một công cụ truy xuất chuyên miền** để một LLM lớn gọi. LLM giữ hội
thoại, quyết định cần tra cứu và viết câu trả lời; công cụ chỉ chịu trách nhiệm
đưa về dữ kiện học vụ có nguồn.

Sự phân công này giữ ontology ở đúng vai trò: nguồn tri thức kiểm chứng được,
không phải trí nhớ phụ của model.

## Đơn vị truy xuất là trọn node

Hình dạng chính là “tìm đúng node rồi lấy trọn node”. Một node thủ tục
được trả cùng nhãn, yêu cầu, bước thực hiện, nơi nộp, thời hạn, kết quả, quan hệ
tiếp theo và nguồn nếu các dữ kiện đó tồn tại.

LLM lớn nhận context rộng hơn câu hỏi hiện tại rồi tự chọn phần cần diễn đạt.
Công cụ không cần duy trì nhiều query gần giống nhau chỉ để lấy riêng từng cạnh
của cùng một node. Shape chuyên biệt chỉ còn cần khi thực sự không thể biểu diễn
bằng node đầy đủ.

## Bảng là một node nguyên văn

Một bảng pháp quy có ý nghĩa nhờ cả hàng, cột, tiêu đề và ô rỗng. Tách từng ô
thành các node kỹ thuật tạo ra một bản chép thứ hai và có thể làm lệch cột.

Mỗi bảng được giữ trong một node với `verbatimTableText`. Khi bảng liên quan, công
cụ trả toàn khối Markdown cùng trích dẫn và URL. Những thực thể được phần khác
của đồ thị tham chiếu, như ngành hoặc chứng chỉ, vẫn tồn tại; nhưng ánh xạ nằm
trong bảng không được chép thêm thành một hệ quan hệ song song.

## Ranh giới trách nhiệm

| Thành phần | Làm | Không làm |
|---|---|---|
| LLM lớn | hiểu hội thoại, gọi công cụ, tổng hợp câu trả lời | tự bịa dữ kiện học vụ khi công cụ không trả về |
| Công cụ ontology | ánh xạ yêu cầu sang query hợp lệ, lấy node và nguồn | viết câu trả lời tự nhiên cuối |
| Danh mục truy vấn | giới hạn các shape được phép chạy | xếp hạng query gần đúng |
| Ontology | giữ nội dung và nguồn | học từ hội thoại |
| Dataset | cung cấp ví dụ ánh xạ câu hỏi sang shape | quyết định sự thật học vụ |

## Từ chối

Công cụ trả không có dữ liệu khi yêu cầu ngoài phạm vi, không xác định được node,
query không khớp danh mục, query không an toàn hoặc kết quả rỗng. LLM phải nói
rõ giới hạn đó, không dùng kiến thức nhớ sẵn để lấp chỗ trống.

Lỗi hạ tầng và lỗi lập trình phải đi theo kênh lỗi, không được giả thành một kết
quả “không có dữ liệu”.

## Thứ tự xây dựng

```text
văn bản chính thức
  → ontology
  → danh mục khả năng trả lời
  → danh mục truy vấn lấy trọn node
  → dataset ví dụ gọi công cụ
  → đánh giá LLM + công cụ
```

Không được viết dataset trước rồi sửa ontology cho khớp. Sự thật học vụ chỉ đến
từ nguồn và ontology.

## Model cũ

Quy trình seq2seq trước đó đã ngừng vì dataset nền bị hỏng. Metric của nó không phải
baseline và model không phải phương án lui. `docs/TRAINING.md` chỉ lưu lại luồng
thực nghiệm lịch sử, không công bố kết quả.

## Tài liệu liên quan

- [Kiến trúc](ARCHITECTURE.md)
- [Ontology](ONTOLOGY.md)
- [Dataset](DATASET.md)
- [Đánh giá](EVALUATION.md)
