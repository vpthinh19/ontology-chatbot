# Đặc tả dataset production

## Mục tiêu

Dataset huấn luyện một model chuyển câu hỏi tiếng Việt thành SPARQL hoặc marker
`không có thông tin`. Mục tiêu là chatbot hoạt động chính xác trong miền mà
ontology chính thức hỗ trợ và từ chối nhất quán ngoài miền.

## Danh mục được hỗ trợ

- Mỗi target SPARQL đến từ query catalogue xây trên ontology mới.
- Target phải parse, vượt kiểm tra an toàn, thực thi và trả ít nhất một dòng.
- Mọi SPARQL mà chatbot công bố hỗ trợ phải xuất hiện trong train.
- Validation/test giữ lại cách diễn đạt, không giữ lại logic query chưa dạy.
- Ngoài catalogue hoặc thiếu dữ liệu dùng marker từ chối.

## Bản ghi

Mỗi dòng có `id`, `query_id`, `register`, `input`, `target`. Câu trong miền dùng
`query_id` canonical và SPARQL. Mọi câu từ chối dùng:

```json
{"id":"question-0002","query_id":"no-information","register":"neutral","input":"xin chào","target":"không có thông tin"}
```

Không thêm trường nhãn phân loại vì target đã xác định đầy đủ hành vi model.

## Phân chia dữ liệu

Train, validation và test cùng phủ catalogue SPARQL và các nhóm từ chối, nhưng
không chia sẻ câu hỏi sau preprocessing. Với cùng `query_id`, câu gần trùng
không được nằm ở hai split. Câu có khung giống nhau nhưng tham chiếu hai query
khác phải được báo cáo để rà soát thủ công.

Cả bốn register phải hiện diện ở hai phía trong/ngoài miền. Câu hỗn hợp, mơ hồ,
gần miền nhưng thiếu dữ liệu và câu người dùng thực tế là các nhóm bắt buộc,
không chỉ dùng negative ngoài chủ đề dễ phân biệt.

## Cổng chất lượng

1. Schema, ID và mapping `query_id → target` nhất quán.
2. SPARQL parse, an toàn, chạy có kết quả trên ontology đúng checksum.
3. Marker trùng chính xác `không có thông tin`.
4. Không leakage giữa split.
5. Phân bố register, in/out-domain và negative group được báo cáo.
6. Source/target round-trip qua cả ba tokenizer.
7. Mọi câu trong `resources/cases/user_queries.txt` được gán nhãn và có ca hồi
   quy tương ứng.

## Nghiệm thu model

Fine-tune T5Gemma2 trước để xác nhận dataset và contract có thể học. Chỉ sau khi
pipeline hợp lệ mới chạy BARTpho và ViT5 cùng giao thức. Benchmark phải công bố
In-domain Answer Exact, marker exact, false acceptance, mixed-query rejection
và System Answer Exact; không chỉ dùng một accuracy tổng hợp.

Không chạy nhiều seed, dò hyperparameter hoặc sửa test theo prediction của
model. Khi chất lượng thiếu, phân tích theo `query_id`/negative group và chỉ sửa
nguồn dữ liệu có bằng chứng.
