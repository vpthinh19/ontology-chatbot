# Đặc tả dataset cho chatbot ontology

## Mục tiêu

Dataset huấn luyện model chuyển câu hỏi tiếng Việt sang một truy vấn SPARQL
thuộc danh mục được hệ thống hỗ trợ. Mục tiêu chính là chatbot truy vấn ontology
chính xác trong miền học vụ đã công bố, không phải kiểm tra khả năng sáng tạo
một cấu trúc SPARQL chưa được dạy.

Model được phép học thuộc ánh xạ từ ý nghĩa câu hỏi sang SPARQL. Model không học
thuộc câu trả lời: label, nội dung, email, học phí và các literal khác vẫn được
lấy từ ontology khi backend thực thi truy vấn.

## Danh mục truy vấn được hỗ trợ

- Danh mục gồm các target SPARQL canonical đã có trong dataset và đã được xác
  minh trên ontology.
- Mỗi target phải parse được, vượt kiểm tra an toàn, thực thi thành công và trả
  về ít nhất một dòng.
- Mọi target mà chatbot tuyên bố hỗ trợ phải xuất hiện trong train.
- Validation và test không chứa target nằm ngoài danh mục train.
- Việc tự ghép một target SPARQL chưa từng xuất hiện trong train không thuộc
  yêu cầu chất lượng của hệ thống.
- Refactor đầu tiên chỉ tái sử dụng 215 target và 1.416 câu hỏi hiện có; không
  tạo thêm target SPARQL.

## Bản ghi dữ liệu

Mỗi dòng JSON Lines có đúng năm trường:

```json
{
  "id": "question-0001",
  "query_id": "query-0001",
  "register": "formal",
  "input": "Tôi cần thực hiện thủ tục bảo lưu như thế nào?",
  "target": "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"
}
```

`query_id` định danh một truy vấn canonical và ánh xạ một-một tới `target`.
Nhiều câu hỏi có cách diễn đạt khác nhau được phép dùng chung `query_id`.
Khái niệm `family_id` cũ được bỏ vì cùng một target phải xuất hiện có chủ ý ở
cả train, validation và test.

`register` tiếp tục có bốn giá trị:

- `formal`: văn phong hành chính đầy đủ;
- `neutral`: cách hỏi phổ thông;
- `colloquial`: ngôn ngữ nói thường ngày;
- `noisy`: viết tắt, bỏ dấu hoặc câu rút gọn.

## Train, validation và test

Ba split cùng phủ một danh mục target nhưng dùng các câu hỏi khác nhau:

- **Train** dạy model toàn bộ SPARQL được hỗ trợ.
- **Validation** chọn checkpoint bằng cách diễn đạt chưa xuất hiện trong train.
- **Test** đo chất lượng cuối bằng cách diễn đạt chưa xuất hiện trong train và
  validation.

Với mỗi `query_id` có đúng một câu validation, một câu test và toàn bộ câu còn
lại thuộc train. Với 1.416 câu hiện có, cách chia này tạo 986 câu train, 215 câu
validation và 215 câu test; mỗi query có ít nhất hai câu train. Việc phân bổ
register được xoay vòng giữa các query để mỗi split có phân bố formal, neutral,
colloquial và noisy cân bằng trên toàn tập;
không cố định toàn bộ câu noisy vào test. Trong mỗi split, chênh lệch số câu
giữa register nhiều nhất và ít nhất không vượt quá một.

Target trùng giữa các split là chủ ý của thiết kế. Những dạng rò rỉ sau vẫn bị
cấm:

- câu `input` trùng sau chuẩn hóa;
- câu gần trùng chỉ khác dấu câu, viết hoa hoặc khoảng trắng;
- một `query_id` ánh xạ tới nhiều target;
- cùng một target ánh xạ tới nhiều `query_id`.

## Tiêu chí chất lượng dữ liệu

Dataset chỉ sẵn sàng huấn luyện khi:

1. mọi bản ghi đúng schema và mọi ID là duy nhất;
2. toàn bộ 215 `query_id` xuất hiện trong cả ba split;
3. mỗi target đạt cổng parse, an toàn, thực thi và kết quả khác rỗng;
4. không có câu trùng hoặc gần trùng giữa các split;
5. bốn register được phân bố cân bằng theo từng split;
6. source và target round-trip qua tokenizer của các model được benchmark mà
   không có `<unk>` và không bị cắt;
7. báo cáo công khai mô tả đúng số câu, query, register và split từ file thật.

## Đánh giá model và hệ thống

Metric chính là Answer Exact sau khi query dự đoán được thực thi trên ontology.
Tên biến và thứ tự dòng không quan trọng, nhưng toàn bộ giá trị, RDF datatype,
language tag, số cột và cách ghép giá trị trong từng dòng phải đúng.

Ngưỡng chấp nhận ban đầu cho model production là ít nhất 95% Answer Exact trên
test trong miền. Parse rate, execution rate, Result precision/recall/F1 và lỗi
theo register/query được giữ làm metric chẩn đoán.

Test chỉ đo những chức năng đã được dạy. Điểm này phải được ghi rõ trong README
để người đọc không diễn giải kết quả thành khả năng tổng quát tới truy vấn hoặc
ontology chưa biết.

Khi split thay đổi, toàn bộ metric và biểu đồ model từ split cũ hết hiệu lực và
phải được gỡ khỏi báo cáo công khai. Kết quả T5Gemma2 dùng làm cổng nghiệm thu
không được công bố riêng như benchmark hoàn chỉnh; báo cáo so sánh chỉ được
sinh lại sau khi đủ ba model chạy trên cùng dataset.

## Trình tự nghiệm thu

1. Tái chia dữ liệu hiện có và chạy toàn bộ cổng chất lượng mà chưa train model.
2. Công bố báo cáo split mới để kiểm tra trước khi dùng GPU.
3. Fine-tune T5Gemma2 đúng một lần với giao thức đã chốt.
4. Nếu T5Gemma2 đạt ngưỡng 95%, mới fine-tune BARTpho và ViT5 để so sánh.
5. Nếu chưa đạt, dừng trước hai model còn lại; phân tích lỗi theo `query_id` và
   chỉ bổ sung cách diễn đạt cho những query thiếu dữ liệu.

Không chạy nhiều seed, không dò hyperparameter và không tự khởi động lại một
model sau lỗi chất lượng. Lỗi kỹ thuật chỉ được tiếp tục từ artifact hợp lệ khi
không làm thay đổi dữ liệu hoặc giao thức.

## Phạm vi không thực hiện

- Sinh target SPARQL chưa có trong danh mục train.
- Đánh giá zero-shot trên schema hoặc ontology khác.
- Thêm fuzzy matching, QueryPlan, traversal hoặc tầng tự sửa query.
- Thay đổi ontology chỉ để làm điểm model cao hơn.
- Tạo hàng loạt câu hỏi mới trước khi kết quả T5Gemma2 chứng minh là cần thiết.
