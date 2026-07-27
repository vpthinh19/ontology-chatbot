# Đặc tả dataset và benchmark SPARQL

## 1. Mục tiêu dữ liệu

Dataset học ánh xạ:

```text
câu hỏi tiếng Việt → SELECT SPARQL canonical
```

Ontology mới là nguồn sự thật cho mọi IRI, property và đáp án. Dataset không
định nghĩa lại schema và backend không suy diễn target bằng heuristic.

## 2. Tái sử dụng dataset cũ

Khoảng 1.000 sample cũ chứa phần tốn công nhất: câu hỏi tự nhiên, cách nói đời
thường, từ viết tắt và tình huống học vụ. Chúng được tái sử dụng theo quy tắc:

| Thành phần | Xử lý |
|---|---|
| Câu hỏi đầu vào | Giữ sau review ngữ nghĩa/ngôn ngữ |
| Register và semantic family | Giữ hoặc sửa nếu đã gán sai |
| Split | Kiểm tra lại leakage theo family |
| QueryPlan/JSON target | Bỏ và gán lại thành SPARQL |
| Canonical ID cũ | Ánh xạ sang ontology mới |
| Capability cũ | Chỉ dùng như gợi ý kiểm kê, không là contract mới |

Không chuyển target hàng loạt rồi mặc định là đúng. Script có thể tạo bản nháp
từ mapping minh bạch, nhưng mỗi nhóm ngữ nghĩa phải được người biên soạn duyệt
và thực thi trên ontology mới.

## 3. Schema record đề xuất

Giữ JSONL làm định dạng lưu dataset vì dễ kiểm tra và không phải output model:

```json
{
  "id": "train-0001",
  "family_id": "academic-leave-condition-01",
  "register": "colloquial",
  "query_shape": "direct",
  "input": "tui sắp đi nghĩa vụ quân sự, muốn bảo lưu thì cần gì",
  "target": "SELECT ?answer WHERE { :AcademicLeaveProcedure :condition ?answer . }"
}
```

Các field tối thiểu:

- `id`: duy nhất và ổn định;
- `family_id`: nhóm các paraphrase cùng tình huống ngữ nghĩa;
- `register`: `formal`, `neutral`, `colloquial`, `noisy`;
- `query_shape`: dạng truy vấn dùng để phân tích phân bố và lỗi;
- `input`: câu nguyên bản trước chuẩn hóa;
- `target`: SPARQL canonical một dòng, không có prefix.

Không bắt buộc `capability_id`. Split được xác định duy nhất bởi tên file
`train.jsonl`, `val.jsonl` hoặc `test.jsonl`, không lặp lại trong từng record.
`query_shape` là metadata đánh giá, không phải target mà model phải học.

## 4. Quy tắc target SPARQL

1. Chỉ dùng `SELECT`.
2. Không chứa `PREFIX`; backend thêm prefix cố định.
3. Một dòng, một khoảng trắng canonical giữa các token.
4. Dùng canonical IRI cho tài nguyên đã biết.
5. Mọi cột được chọn phải là label, literal hoặc aggregate.
6. Không chọn URIRef/blank node làm đáp án cuối.
7. Câu hỏi nhiều yêu cầu phải có đủ biến/cột hoặc nhánh tương ứng.
8. `content` dùng cho yêu cầu hướng dẫn tổng quát; property cụ thể dùng cho
   câu hỏi cụ thể.

Ví dụ nhiều thuộc tính của hai quy trình:

```sparql
SELECT ?procedure ?condition WHERE { VALUES ?node { :AcademicLeaveProcedure :GraduationReviewProcedure } ?node rdfs:label ?procedure ; :condition ?condition . }
```

Ví dụ lọc học phí:

```sparql
SELECT ?answer WHERE { ?rate a :TuitionRate ; :cohortCode ?cohort ; :programName ?program ; :tuitionPerCredit ?answer . FILTER ( STR ( ?cohort ) = "K63" ) FILTER ( STR ( ?program ) = "Công nghệ sinh học" ) }
```

Ví dụ đếm:

```sparql
SELECT (COUNT(DISTINCT ?method) AS ?answer) WHERE { :TuitionPaymentProcedure :supportsPaymentMethod ?method . }
```

## 5. Chuẩn hóa đầu vào

Giữ nguyên `input` trong dataset. Một normalizer dùng chung cho train và
inference chỉ được:

- chuẩn hóa Unicode và khoảng trắng;
- mở rộng whitelist viết tắt chắc nghĩa trong miền học vụ;
- giữ nguyên từ đa nghĩa nếu thiếu ngữ cảnh.

Ví dụ có thể chuẩn hóa `nvqs` thành `nghĩa vụ quân sự`. Không đưa entity
resolution, alias lookup hoặc fuzzy matching vào preprocessing.

## 6. Chia dữ liệu và đóng gói release

Một semantic family là cùng tình huống và cùng nhu cầu thông tin được diễn đạt
theo nhiều cách. Toàn bộ family phải nằm trong một split.

Không được đặt câu formal ở train rồi đưa bản viết tắt/noisy của chính câu đó
vào validation. Exact dedup chỉ là cổng tối thiểu; near-duplicate ngữ nghĩa cần
review thủ công.

Benchmark cuối:

- được viết/review độc lập sau khi ontology và target contract ổn định;
- không dùng để chọn epoch, learning rate, normalizer hoặc sửa dataset;
- nếu có lỗi dữ liệu thật, tạo version mới và ghi lý do;
- không sao chép hoặc paraphrase câu benchmark vào train.

Các câu benchmark QueryPlan cũ có thể làm nguồn biên soạn, nhưng target và
manifest cũ không còn hợp lệ.

Một release có cấu trúc cố định:

```text
resources/datasets/sparql_v2/
├── train.jsonl
├── val.jsonl
├── test.jsonl
├── manifest.json
└── README.md
```

Ba file JSONL có cùng schema. `manifest.json` khóa số lượng, phân bố và
checksum; `test.jsonl` thay thế khái niệm thư mục benchmark riêng trước đây.

## 7. Cổng kiểm tra tự động

Trước khi train, mọi record phải vượt:

- JSONL đúng schema, ID duy nhất;
- không trùng input sau chuẩn hóa;
- không rò `family_id` giữa split;
- SPARQL parse được sau khi gắn prefix;
- query chỉ đọc và không dùng `SERVICE`;
- mọi IRI/property tồn tại trong ontology mới;
- query thực thi không lỗi và reference answer đã được duyệt;
- tokenizer của cả BARTpho và ViT5 không sinh `<unk>` cho token cấu trúc;
- encode/decode target giữ đúng query canonical.

Query trả rỗng không tự động là lỗi vì một câu phủ định có thể hợp lệ, nhưng
phải được đánh dấu và review thay vì lọt qua im lặng.

## 8. Learning audit trước train đầy đủ

Dùng một tập rất nhỏ nhưng phủ các shape:

- lấy `content`;
- lấy datatype trực tiếp;
- đi object property rồi lấy label;
- đi object property rồi lấy datatype;
- nhiều cột/nhiều nhánh;
- `FILTER`/literal constraint;
- `COUNT` hoặc aggregate.

Mục đích là chứng minh tokenizer, collator, label masking và generation hoạt
động; không dùng điểm này để tuyên bố khả năng tổng quát hóa. Cả hai model phải
overfit gần như hoàn toàn tập train nhỏ và sinh query parse/thực thi được trước
khi chạy dataset đầy đủ.

## 9. Metrics benchmark

Các metric bắt buộc:

- `parse_rate`: SPARQL parse được;
- `execution_rate`: query chạy không lỗi;
- `answer_exact_rate`: tập hàng/cột sau chuẩn hóa bằng reference;
- `canonical_query_exact_rate`: chuỗi query canonical khớp target;
- kết quả theo `register` và `query_shape`;
- lỗi riêng cho sai IRI, sai property, thiếu nhánh, thừa nhánh và sai literal.

`answer_exact_rate` là metric đầu-cuối chính. `canonical_query_exact_rate` vẫn
cần báo cáo vì hai query tình cờ trả cùng kết quả trên ontology nhỏ chưa chắc
có cùng ý nghĩa.

So sánh BARTpho, ViT5 và T5Gemma2 trên cùng split, normalizer, target, decoding
policy và generation budget. Benchmark v2 dùng một seed cố định là 42; báo cáo
seed, optimizer step, thời gian và VRAM cực đại. Không mặc định chạy nhiều seed.

## 10. Không đặt mục tiêu số lượng máy móc

Không giữ 1.000 sample chỉ vì con số đẹp và cũng không vứt chúng đi. Sau khi
gán lại target:

- bỏ câu sai hoặc mơ hồ không thể sửa hợp lý;
- bổ sung family khi coverage hoặc error analysis chứng minh đang thiếu;
- không nhồi paraphrase để che một điểm yếu schema;
- ưu tiên độ đúng target và độ đa dạng tình huống hơn tổng số dòng.

## 11. Trạng thái release dataset SPARQL v1

Bản chuyển đổi hiện tại có 948 câu dùng để phát triển model:

- 948 câu và 237 semantic family;
- 636 câu train, 312 câu validation (`val.jsonl`);
- bốn register cân bằng chính xác, mỗi register 237 câu;
- 80 target SPARQL canonical;
- 900 câu được giữ từ production QueryPlan sau khi gán lại target;
- 48 câu `COUNT`/`FILTER` được viết thủ công có mục tiêu;
- 60 câu `greeting`/`unrelated`/`clarify` bị loại khỏi core SPARQL.

Toàn bộ 948 target parse và thực thi có kết quả trên ontology v11. Cả 80 target
duy nhất round-trip chính xác trên BARTpho và ViT5, không có `<unk>`; độ dài
target tối đa lần lượt là 91 và 123 token. Đây là tổng của `train.jsonl` và
`val.jsonl`, không bao gồm test cuối.

## 12. Test SPARQL v1 đã đóng băng

Test cuối nằm tại `resources/datasets/sparql_v1/test.jsonl` và có 164 câu
không trùng chính xác với train/val:

| Query shape | Số câu |
|---|---:|
| direct | 78 |
| graph_hop | 54 |
| multi_column | 16 |
| aggregate | 8 |
| aggregate_filter | 8 |

Bốn register có đúng 41 câu mỗi loại. 148 câu hỏi độc lập được giữ lại từ bộ
benchmark cũ sau khi bỏ target QueryPlan và gán lại SPARQL v11; 36 câu hội
thoại ngoài core bị loại. 16 câu `COUNT`/`FILTER` mới được biên soạn riêng,
không lấy từ train/validation.

Toàn bộ reference parse, thực thi có kết quả và self-check đạt 100%. Cả 80
target duy nhất round-trip đúng trên hai tokenizer, không có `<unk>`. Manifest
khóa số liệu và checksum tại `resources/datasets/sparql_v1/manifest.json`.

Benchmark chỉ được mở để chấm checkpoint đã chọn bằng validation. Lệnh không
có `--predictions` chỉ self-check evaluator bằng reference, không phải kết quả
model:

```bash
uv run benchmark_sparql
uv run benchmark_sparql --predictions artifacts/predictions.jsonl --output artifacts/benchmark.json
```

Kết quả chính thức 2 model × 3 seed được khóa trong
`SPARQL_EXPERIMENT_V1.md`. Benchmark v1 không được dùng tiếp để chỉnh dataset
hoặc chọn hyperparameter.

Quy trình thi công release chất lượng tiếp theo được khóa tại
`DATASET_UPGRADE_PLAN.md`. Khi hai tài liệu khác nhau về cách thực hiện, file
này định nghĩa contract dữ liệu còn kế hoạch nâng cấp định nghĩa thứ tự và cổng
review.
