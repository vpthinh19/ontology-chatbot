# Mở rộng độ phủ dataset

## Mục tiêu

Dataset phải dạy đầy đủ các cách diễn đạt trong miền ontology và đo chất lượng
ổn định hơn trên câu hỏi chưa xuất hiện trong train. Ngưỡng nghiệm thu của
chatbot là Answer Exact lớn hơn 90% trên test đã khóa.

Danh mục chức năng vẫn gồm 215 `query_id` ánh xạ một-một tới 215 SPARQL
canonical. Việc mở rộng chỉ bổ sung câu hỏi tiếng Việt, không tạo query mới,
không sửa ontology và không thay đổi pipeline model.

## Mở rộng validation và test

Mỗi query có hai câu validation và hai câu test độc lập thay vì một câu:

- validation tăng từ 215 lên 430 câu;
- test tăng từ 215 lên 430 câu;
- câu bổ sung của một query dùng register khác câu đã có;
- mỗi split vẫn cân bằng `formal`, `neutral`, `colloquial` và `noisy`, chênh
  lệch giữa register nhiều nhất và ít nhất không quá một;
- câu validation và test không được sao chép hoặc diễn đạt gần sát câu train
  hay câu ở split khác;
- test được khóa sau khi biên soạn và không được dùng để lựa chọn dữ liệu,
  checkpoint hoặc tham số.

Validation được phép dùng để chẩn đoán lỗi và chọn checkpoint. Test chỉ được
thực thi một lần sau khi model và dataset train đã được chốt.

## Mở rộng train

Độ phủ train được xét theo ma trận `query_id × register`. Trạng thái hiện tại
còn thiếu 219 ô trên 110 query, gồm 44 `colloquial`, 65 `formal`, 58 `neutral`
và 52 `noisy`.

Quá trình bổ sung gồm hai lớp:

1. Thêm đúng một câu độc lập cho từng ô còn thiếu, đưa train từ 1.150 lên
   1.369 câu và bảo đảm mỗi query có ít nhất một câu ở cả bốn register.
2. Chạy checkpoint T5Gemma2 hiện tại trên validation mở rộng. Với mỗi kiểu lỗi
   validation khác nhau của một query, thêm một câu train độc lập làm rõ đúng
   property, IRI, literal, phép toán hoặc số nhánh bị nhầm. Không sao chép câu
   validation và không dùng prediction trên test.

Số câu train cuối của lớp thứ hai được suy ra từ lỗi validation thật, không đặt
chỉ tiêu số lượng tùy ý.

## Nguyên tắc biên soạn

- Câu hỏi phải tự nhiên và đủ nghĩa trong register đã gán.
- `noisy` có thể không dấu, viết tắt hoặc rút gọn nhưng không được biến thành
  chuỗi từ khóa mơ hồ.
- Mỗi ý được hỏi phải tương ứng chính xác với một nhánh kết quả trong target;
  không gợi ý thêm property ngoài target.
- Các cặp `content`/`condition`/`outcome`, `handledBy`/`receivedBy`, label/literal
  và document/document URL phải được phân biệt bằng ngữ nghĩa rõ ràng.
- Query có `FILTER`, `COUNT`, `AVG`, `GROUP BY`, `ORDER BY`, `LIMIT` hoặc
  `VALUES` phải thể hiện đủ toán tử, phạm vi, giá trị và trường cần trả về.
- Viết tắt đa nghĩa như `dk` và `hp` chỉ được dùng khi phần còn lại của câu đủ
  ngữ cảnh để giải nghĩa.
- Target của câu mới phải trùng byte với target canonical đã có của `query_id`.

## Kiểm định

Dataset chỉ được chấp nhận khi:

1. mọi bản ghi đúng schema, ID duy nhất và ánh xạ query-target một-một;
2. train có đủ bốn register cho từng query;
3. validation và test có đúng hai câu cho từng query;
4. register cân bằng riêng trong từng split;
5. không có input trùng hoặc gần trùng giữa các split;
6. mọi target parse được, an toàn, thực thi được và trả kết quả;
7. source và target vượt audit tokenizer BARTpho, ViT5 và T5Gemma2 mà không có
   `<unk>` hoặc bị cắt;
8. manifest, tài liệu và biểu đồ được sinh lại từ file vật lý;
9. test mới chưa được model thực thi trong quá trình bổ sung train.

## Trình tự nghiệm thu model

Sau khi dataset vượt toàn bộ cổng chất lượng:

1. fine-tune T5Gemma2 đúng một lần với giao thức đã chốt;
2. chọn checkpoint bằng validation 430 câu;
3. benchmark một lần trên test 430 câu;
4. nếu Answer Exact lớn hơn 90%, khóa dataset và huấn luyện BARTpho, ViT5;
5. nếu chưa đạt, dừng để đánh giá giới hạn model, không tiếp tục điều chỉnh theo
   lỗi test.

## Ngoài phạm vi

- Tạo SPARQL hoặc chức năng ontology mới.
- Sửa ontology, normalizer, backend hoặc tham số huấn luyện.
- Sinh dữ liệu hàng loạt bằng template hoặc script thay cho biên soạn nội dung.
- Chạy nhiều seed, dò hyperparameter hoặc tối ưu dataset theo prediction test.
