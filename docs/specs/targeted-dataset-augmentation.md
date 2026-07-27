# Bổ sung có mục tiêu cho dataset

## Mục tiêu

Bổ sung dữ liệu huấn luyện cho 41 truy vấn mà T5Gemma2 chưa trả lời chính xác
trên tập test, tập trung vào nhận diện đúng property và đúng số nhánh kết quả.
Đây là mở rộng cách diễn đạt trong miền đã hỗ trợ, không mở rộng danh mục truy
vấn hoặc ontology.

## Phạm vi dữ liệu

- Giữ nguyên từng byte của `val.jsonl` và `test.jsonl` để kết quả huấn luyện sau
  có thể so sánh trực tiếp với mốc Answer Exact 80,93%.
- Chỉ thêm bản ghi vào `train.jsonl`.
- Giữ nguyên 215 ánh xạ `query_id` sang SPARQL canonical.
- Không tạo target SPARQL mới, không sửa ontology và không thay đổi normalizer.
- Không sao chép hoặc diễn đạt lại gần sát câu validation và test.

## Nội dung bổ sung

Mỗi một trong 41 `query_id` thất bại được bổ sung bốn câu hỏi độc lập, mỗi câu
thuộc một register:

- `formal`: câu hành chính đầy đủ;
- `neutral`: câu hỏi phổ thông, rõ nghĩa;
- `colloquial`: lời nói tự nhiên thường ngày;
- `noisy`: có thể viết tắt, không dấu hoặc rút gọn nhưng vẫn phải đủ thông tin
  để xác định duy nhất target.

Tổng cộng thêm 164 bản ghi. Train tăng từ 986 lên 1.150 câu và toàn dataset
tăng từ 1.416 lên 1.580 câu. Mỗi register của train tăng đúng 41 câu nên phân bố
toàn tập vẫn cân bằng.

## Nguyên tắc biên soạn

1. Câu hỏi phải tự nhiên trong tiếng Việt và không mô tả trực tiếp cú pháp
   SPARQL.
2. Mỗi ý người dùng yêu cầu phải tương ứng với một nhánh kết quả của target.
3. Không thêm tín hiệu khiến model hợp lý khi trả về một property ngoài target.
4. Các cặp dễ nhầm như `content`/`condition`/`outcome`,
   `handledBy`/`receivedBy` và label/property literal phải dùng từ ngữ phân biệt
   rõ vai trò.
5. Query có `FILTER`, `COUNT`, `GROUP BY`, `ORDER BY`, `LIMIT` hoặc `VALUES`
   phải thể hiện đầy đủ phép toán, giá trị và phạm vi trong câu hỏi.
6. Viết tắt đa nghĩa như `dk` và `hp` chỉ được dùng khi phần còn lại của câu đủ
   ngữ cảnh để giải nghĩa; không mở rộng whitelist normalizer cho chúng.
7. Câu `noisy` không được trở thành chuỗi từ khóa vô nghĩa hoặc câu đố thiếu dữ
   kiện.

## Kiểm định

Dataset sau bổ sung chỉ được chấp nhận khi:

- `val.jsonl` và `test.jsonl` giữ nguyên SHA-256;
- schema, ID và ánh xạ `query_id`/target hợp lệ;
- không có input trùng hoặc gần trùng giữa các split;
- toàn bộ SPARQL parse được, an toàn, thực thi được và trả kết quả;
- mọi input và target đi qua tokenizer của các model benchmark mà không bị
  `<unk>` hoặc cắt;
- manifest và báo cáo phân bố được sinh lại từ dữ liệu thực;
- các kiểm thử dataset hiện có đều vượt qua.

## Ngoài phạm vi

- Fine-tune hoặc benchmark lại model trong lượt bổ sung dữ liệu này.
- Dò hyperparameter, chạy nhiều seed hoặc thay đổi giao thức huấn luyện.
- Điều chỉnh câu validation/test theo prediction của model.
- Thêm fuzzy matching, sửa SPARQL hậu kỳ hoặc logic chữa lỗi ở backend.
