# Candidate pool và dataset hợp nhất đích

## Mục tiêu

Dataset chính thức sẽ dạy một model seq2seq thực hiện trọn luồng quyết định:

- câu được ontology hỗ trợ → sinh SPARQL `SELECT`;
- câu không được hỗ trợ → sinh `không có thông tin`.

Ontology và inventory khả năng trả lời đã được xác nhận. Dataset chỉ được khóa
sau khi query catalogue chính thức phủ các mục `supported` trong inventory và
mọi target được kiểm tra lại trên graph canonical.

455 câu đang nằm trong repository là candidate pool phục vụ smoke và curation.
Mỗi câu sẽ được giữ, sửa hoặc loại sau audit; không bản ghi nào tự động mang
trạng thái official chỉ vì đã vượt validator hiện tại.

## Tổ chức file

```text
resources/dataset/main/
├── catalogue.jsonl
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
  "id": "question-000001",
  "query_id": "procedure-instruction",
  "register": "formal",
  "input": "Tôi cần thực hiện thủ tục bảo lưu như thế nào?",
  "target": "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . }"
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

`query_id` chọn một template trong catalogue. Các slot IRI hoặc số được thế vào
template, vì vậy một họ truy vấn có thể có nhiều target canonical. Mọi câu từ
chối dùng `no-information`. `register` có bốn giá trị:

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

`resources/cases/user_queries.txt` và `test.html` lưu câu đã được người dùng thử
trên giao diện. Đây là nguồn cách diễn đạt và ca hồi quy, không phải nguồn dữ
kiện ontology. Mỗi input có ý nghĩa phải được đối chiếu lại với ontology và
catalogue canonical trước khi đưa vào split; file nguồn không được loader tự
động xem là dữ liệu train.

## Train, validation và test

Mỗi SPARQL canonical phải xuất hiện trong train. Validation và test đo cách
diễn đạt chưa thấy cho những chức năng đã được dạy, không tuyên bố zero-shot
trên schema mới. Dataset đích được biên soạn theo ma trận:

```text
query family × entity/slot × cách diễn đạt × register × split
```

Mọi family xuất hiện trong ba split; train phủ đủ bốn register cho từng family.
Các family quy trình trọng tâm phải có formal, neutral, colloquial và noisy ở
cả validation/test. Phân bố held-out phải cân bằng theo miền/register thay vì
tách gần như toàn bộ formal/colloquial sang validation và neutral/noisy sang
test.

Snapshot candidate hiện có 455 câu: 339 train, 58 validation và 58 test; gồm 24
họ truy vấn, trong đó 96 câu mang marker từ chối. Đây không phải kích thước mục
tiêu. Dataset chỉ dừng tăng khi ma trận coverage không còn vùng trắng quan
trọng. Các quy tắc leakage:

1. ID là duy nhất toàn bộ dataset.
2. Câu trùng sau `normalize_model_input` không được nằm ở hai split.
3. Câu gần trùng cùng `query_id` không được nằm ở hai split.
4. Câu có khung giống nhau nhưng query khác chỉ được báo cáo để rà soát, không
   tự động xem là leakage.
5. Test không được dùng để bổ sung dữ liệu hoặc chọn checkpoint.

## Kiểm soát chất lượng

Candidate hiện tại chỉ đủ cho smoke/pilot có giới hạn. Dataset chính thức chỉ
sẵn sàng full fine-tuning khi:

1. mọi mục `supported` trong ontology inventory có catalogue và coverage;
2. mọi bản ghi đúng schema, nhãn và target;
3. target trong miền parse, vượt contract an toàn, chạy có kết quả;
4. target ngoài miền trùng chính xác `không có thông tin`;
5. không có leakage theo quy tắc split;
6. register và nhóm trong/ngoài miền được báo cáo rõ;
7. toàn bộ source/target round-trip qua tokenizer của cả ba model, không `<unk>`
   ở token cấu trúc và không bị cắt;
8. manifest/checksum được sinh từ file thật sau lần kiểm tra cuối.

Tập ngoài miền phải lớn theo độ phủ hành vi: chào hỏi, chủ đề khác, gần miền
nhưng thiếu dữ liệu, mơ hồ, noisy, mixed và hard negative dùng từ học vụ nhưng
hỏi quan hệ không tồn tại. Không phình dataset bằng câu vô nghĩa hoặc hoán đổi
từ hàng loạt. Dataset lưu input raw; trainer, benchmark và runtime dùng chung
`normalize_model_input`, bao gồm quyết định `hp → học phần`.

Số câu, phân bố, checksum và biểu đồ được sinh từ `manifest.json` và
`reports/dataset.json`, không điền tay từ log huấn luyện.
