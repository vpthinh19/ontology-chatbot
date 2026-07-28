# Dataset hợp nhất

## Mục tiêu

Dataset dạy một model seq2seq thực hiện trọn luồng quyết định:

- câu được ontology hỗ trợ → sinh SPARQL `SELECT`;
- câu không được hỗ trợ → sinh `không có thông tin`.

Dataset chỉ được tạo sau khi ontology và danh mục SPARQL đã được xác nhận từ
tài liệu chính thức.

## Tổ chức file

```text
resources/dataset/main/
├── train.jsonl
├── val.jsonl
├── test.jsonl
└── manifest.json
```

Không có dataset phân loại riêng. Ba split chứa cả câu trong và ngoài miền.

## Schema

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

Câu ngoài miền dùng:

```json
{
  "id": "question-0002",
  "query_id": "no-information",
  "register": "neutral",
  "input": "Ngày mai thời tiết thế nào?",
  "target": "không có thông tin"
}
```

`query_id` ánh xạ một-một tới target canonical. Mọi câu từ chối dùng
`no-information`. `register` có bốn giá trị:

| Register | Cách diễn đạt |
|---|---|
| `formal` | Câu đầy đủ, gần văn phong hành chính |
| `neutral` | Cách hỏi phổ thông |
| `colloquial` | Ngôn ngữ nói thường ngày |
| `noisy` | Viết tắt, bỏ dấu hoặc câu rút gọn |

## Ranh giới nhãn

Một câu chỉ mang target SPARQL khi query catalogue trả lời được trọn vẹn. Target
`không có thông tin` áp dụng cho:

- câu ngoài học vụ;
- câu gần học vụ nhưng ontology thiếu dữ liệu;
- câu mơ hồ hoặc thiếu thực thể bắt buộc;
- chào hỏi, trò chuyện chung và văn bản vô nghĩa;
- câu hỗn hợp có ít nhất một yêu cầu không được hỗ trợ.

Không tạo target trả lời một phần câu hỗn hợp.

## Câu hỏi thực tế

`resources/cases/user_queries.txt` lưu nguyên văn các câu đã được người dùng thử
trên giao diện. Khi ontology mới hoàn tất, từng câu phải được đối chiếu dữ liệu
thật, gán SPARQL hoặc marker rồi đưa vào đúng split. File nguồn tiếp tục được
giữ làm ca hồi quy, không tự động được loader xem là dữ liệu train.

## Train, validation và test

Mỗi SPARQL canonical phải xuất hiện trong train. Validation và test đo cách
diễn đạt chưa thấy cho những chức năng đã được dạy, không tuyên bố zero-shot
trên schema mới. Cả ba split phải có đầy đủ bốn register và các nhóm ngoài miền
quan trọng.

Các quy tắc leakage:

1. ID là duy nhất toàn bộ release.
2. Câu trùng sau `normalize_model_input` không được nằm ở hai split.
3. Câu gần trùng cùng `query_id` không được nằm ở hai split.
4. Câu có khung giống nhau nhưng query khác chỉ được báo cáo để rà soát, không
   tự động xem là leakage.
5. Test không được dùng để bổ sung dữ liệu hoặc chọn checkpoint.

## Kiểm soát chất lượng

Dataset chỉ sẵn sàng huấn luyện khi:

1. mọi bản ghi đúng schema và nhãn;
2. target trong miền parse, vượt contract an toàn, chạy có kết quả;
3. target ngoài miền trùng chính xác `không có thông tin`;
4. không có leakage theo quy tắc split;
5. register và nhóm trong/ngoài miền được báo cáo rõ;
6. toàn bộ source/target round-trip qua tokenizer của cả ba model, không `<unk>`
   ở token cấu trúc và không bị cắt;
7. manifest/checksum được sinh từ file thật sau lần kiểm tra cuối.

Số câu, số query, phân bố và biểu đồ chỉ được công bố từ manifest của dataset
mới, không kế thừa báo cáo hiện tại.
