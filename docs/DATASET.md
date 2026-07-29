# Dataset hợp nhất

## Mục tiêu

Dataset dạy một model seq2seq thực hiện trọn quyết định của chatbot:

- câu được ontology hỗ trợ → sinh một dòng SPARQL `SELECT`;
- câu không được hỗ trợ → sinh chính xác `không có thông tin`.

Nguồn sự thật đi theo một chiều: công văn chính thức → ontology → inventory →
catalogue SPARQL → dataset. Câu hỏi không được dùng để thêm ngược dữ kiện vào
ontology.

## Quy mô và phân bố

Dataset có 2.888 câu, đủ 51 họ truy vấn trong catalogue và coverage hoàn chỉnh.

| Split | Số câu | Vai trò |
|---|---:|---|
| Train | 2.079 | Dạy toàn bộ họ query, schema và giá trị slot hữu hạn |
| Validation | 402 | Chọn checkpoint bằng cách diễn đạt chưa thấy |
| Test | 407 | Đánh giá cuối; không dùng để sửa dữ liệu hay chọn checkpoint |

| Miền | Số câu |
|---|---:|
| Quy trình học vụ | 1.374 |
| Học phí | 295 |
| Quy tắc học vụ | 228 |
| Chứng chỉ | 260 |
| Biểu mẫu | 124 |
| Ngoài miền | 607 |

Bốn phong cách diễn đạt được phân bố gần cân bằng: 748 `formal`, 727 `neutral`,
719 `colloquial` và 694 `noisy`.

### Độ phủ quy trình học vụ

Catalogue có 142 target SPARQL canonical thuộc các họ `procedure-*`. Train có
962 câu cho các target này: mỗi target có ít nhất sáu câu và đủ `formal`,
`neutral`, `colloquial`, `noisy`. Riêng 22 target hướng dẫn có ít nhất sáu câu
hỏi cách thực hiện và bốn câu yêu cầu nội dung tổng quan; đăng ký học phần có
12 câu.

Validation có 180 và test có 185 câu `procedure-*`; cả hai đều phủ đủ 142
target. Mỗi target hướng dẫn có cả câu hỏi cách thực hiện lẫn câu hỏi tổng quan,
còn đăng ký học phần có đủ bốn phong cách trong từng tập. Các số đo và SHA-256
được lưu tại `reports/procedure-dataset.json`.

![Số câu theo split](../reports/figures/dataset-splits.svg)

![Phong cách câu hỏi](../reports/figures/registers.svg)

## Hình dạng một bản ghi

Mỗi dòng JSON Lines có đúng năm trường:

```json
{"id":"question-000001","query_id":"procedure-instruction","register":"formal","input":"Tôi cần thực hiện thủ tục bảo lưu như thế nào?","target":"SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . }"}
```

- `id`: định danh duy nhất của câu hỏi;
- `query_id`: họ logic trong `catalogue.jsonl`;
- `register`: một trong bốn phong cách diễn đạt;
- `input`: câu tiếng Việt tự nhiên, được lưu ở dạng raw;
- `target`: một dòng SPARQL canonical hoặc marker từ chối.

Ví dụ ngoài miền:

```json
{"id":"question-001999","query_id":"no-information","register":"neutral","input":"Ngày mai thời tiết thế nào?","target":"không có thông tin"}
```

`query_id` ánh xạ tới template truy vấn, không nhất thiết ánh xạ một-một tới
chuỗi target vì một họ có thể thay các IRI hoặc ngưỡng số khác nhau.

## Ranh giới trả lời

Một câu chỉ nhận target SPARQL khi ontology trả lời được toàn bộ yêu cầu. Marker
từ chối bao phủ bảy nhóm: chào hỏi/trò chuyện, chủ đề không liên quan, gần miền
nhưng thiếu dữ liệu, câu mơ hồ, câu hỗn hợp, hard negative dùng từ học vụ sai
quan hệ và câu ngoài miền noisy. Backend không trả lời một phần câu hỗn hợp.

607 câu từ chối được chia thành: 99 mơ hồ, 50 chào hỏi/trò chuyện, 158 hard
negative, 80 câu hỗn hợp, 100 câu gần miền nhưng thiếu dữ liệu, 60 câu ngoài
miền noisy và 60 câu không liên quan.

## Chia tập và chống rò rỉ

Mọi họ truy vấn xuất hiện trong cả ba split. Train phủ đủ bốn register cho mỗi
họ và toàn bộ giá trị slot hữu hạn. Validation/test giữ lại cách diễn đạt, không
giấu schema chưa từng được dạy. Các ràng buộc tự động gồm:

1. ID duy nhất trên toàn release;
2. không trùng input sau chuẩn hóa giữa các split;
3. không có câu gần trùng cùng `query_id` đi xuyên split;
4. mọi target trong miền parse, qua contract an toàn, chạy trên ontology và trả
   ít nhất một dòng;
5. mọi target ngoài miền trùng chính xác marker;
6. bảy câu test tay trong `resources/cases/user_queries.txt` xuất hiện đúng một
   lần trong test;
7. test được khóa bằng SHA-256
   `7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305`.

## Tiền xử lý và tokenizer

Dataset giữ nguyên câu đầu vào. Trainer, benchmark và runtime cùng dùng một
normalizer: Unicode NFC, thu gọn khoảng trắng và chỉ mở rộng các viết tắt tiếng
Việt chắc nghĩa, trong đó `hp` là `học phần`. Target dùng khoảng trắng canonical;
toàn bộ source/target phải qua kiểm tra round-trip với tokenizer T5Gemma2 trước
huấn luyện.

## Tái tạo số liệu

`manifest.json`, `reports/dataset.json`, `reports/procedure-dataset.json` và các
SVG mô tả dataset; manifest và biểu đồ tổng quát được sinh trực tiếp từ dữ
liệu. Chạy:

```bash
uv run validate_sparql_dataset
uv run generate_reports
```

Manifest lưu schema, số câu theo split/miền, contract chia tập và SHA-256 của
dataset, catalogue, coverage và ontology.
