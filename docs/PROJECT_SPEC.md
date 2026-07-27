# Đặc tả project — nguồn sự thật

Trạng thái: **đã chốt thiết kế; ontology, runtime và dữ liệu v1 đã chuyển đổi**.

Tài liệu này lưu các quyết định bắt buộc để một lượt làm việc dài hoặc context
bị rút gọn không kéo project quay lại kiến trúc cũ. Nếu một tài liệu, artifact
hay module mâu thuẫn với file này, file này được ưu tiên.

## 1. Mục tiêu

Xây dựng và đánh giá chatbot tiếng Việt dịch câu hỏi học vụ thành SPARQL, sau
đó thực thi query trên ontology RDF để lấy câu trả lời chính xác.

Giả thuyết nghiên cứu tập trung vào khả năng semantic parsing của model và khả
năng truy vấn dữ liệu có quan hệ của ontology. Không cần chứng minh ontology
tốt hơn một cơ sở dữ liệu phẳng.

## 2. Quyết định đã khóa

### Model

- Benchmark `vinai/bartpho-syllable`, `VietAI/vit5-base` và
  `google/t5gemma-2-270m-270m`.
- mBART không thuộc benchmark chính.
- Dynamic padding; không pad cố định toàn dataset.
- BF16 và TF32 trên RTX 4050 Laptop 6 GB.
- `torch.compile=False`.
- Cấu hình riêng của mỗi model được chọn bằng validation, nhưng ba model phải
  dùng cùng dataset, split, target semantics và giao thức benchmark.

### Môi trường thực thi

- Môi trường chuẩn là Fedora Linux x86_64 và Bash.
- Python 3.12 được quản lý bằng `uv`.
- Phần cứng chính là NVIDIA GeForce RTX 4050 Laptop 6 GB; tận dụng CUDA, BF16
  và TF32 cho training.
- Được tận dụng công cụ Linux như `rg`, `jq`, GNU coreutils, `sha256sum`, Git
  và `nvidia-smi` cho các bước deterministic và tái lập được.
- Không thêm lớp tương thích Windows nếu nó làm kiến trúc phức tạp hơn mà đề
  tài không yêu cầu.

### Ontology

- Canonical storage: Turtle `.ttl`.
- Runtime: RDFLib; OWL-RL chỉ dùng khi có phép suy luận cụ thể cần đến nó.
- Tạo phiên bản mới từ `ontology_v10.ttl`, không sửa mất provenance của v10.
- Giữ `content`.
- Làm phẳng duy nhất các wrapper `Condition` và `Outcome` thành datatype
  property lặp `condition` và `outcome`.
- Object property là đường nối, không phải dữ liệu cuối trả cho người dùng.
- Chuẩn hóa URI tiếng Anh và label tiếng Việt; alias chỉ giữ biến thể có ích.

### Output model

- Model sinh trực tiếp một `SELECT` SPARQL.
- Model biết canonical schema và IRI của ontology.
- Target canonical trên một dòng, có khoảng trắng ổn định quanh ký hiệu.
- Prefix cố định do backend thêm, không nằm trong target.
- Kết quả cuối phải project `rdfs:label`, datatype literal hoặc aggregate.
- SPARQL đảm nhận join, nhiều nhánh, filter, count, sort và limit.

### Backend

- Validate query chỉ đọc; không đoán hoặc sửa query sai.
- Thực thi bằng `rdflib.Graph.query()`.
- Kết quả là list các mapping Python đơn giản.
- Không QueryPlan, custom traversal, fuzzy match, gold tree, schema-specific
  result DTO hoặc formatter viết riêng cho từng route.

### Dataset và benchmark

- Tái sử dụng câu hỏi tự nhiên của dataset cũ sau review.
- Không tái sử dụng nguyên trạng target QueryPlan cũ.
- Gán lại toàn bộ target thành SPARQL theo ontology mới.
- Giữ các câu khẩu ngữ và noisy có thật; chuẩn hóa từ viết tắt bằng whitelist
  nhỏ và dùng cùng một hàm ở train/inference.
- Không sinh hàng loạt câu tiếng Việt bằng script. Script chỉ kiểm tra và hỗ
  trợ tạo bản nháp target có thể review.
- Chia dữ liệu theo semantic family để tránh paraphrase leakage.
- Benchmark cuối tách biệt và chỉ đóng băng sau ontology, schema target và
  normalizer.
- Mỗi release dùng ba file tiêu chuẩn `train.jsonl`, `val.jsonl`, `test.jsonl`
  có cùng schema; split không lặp lại trong từng record.
- Metric chính là query thực thi trả đúng kết quả; parse/execution/canonical
  exact là các metric chẩn đoán bắt buộc.
- `sparql_v1` là baseline bất biến. Đợt nâng cấp chất lượng tiếp theo tạo
  `sparql_v2` theo checklist tại `DATASET_UPGRADE_PLAN.md`, không sửa v1 tại chỗ.

## 3. Những thứ tuyệt đối không hồi sinh

- Cây JSON `{act, entities}`.
- QueryPlan `query route ...`.
- Cây vàng, `gold`, traversal tự viết và route grammar.
- Fuzzy matching trong runtime để tìm canonical entity.
- Baseline cơ sở dữ liệu phẳng hoặc RAG thu nhỏ chỉ để tạo phép đối chứng.
- `EntityResult`, `LiteralResult` và tầng DTO theo loại ontology.
- mBART trong benchmark chính.
- Kết luận cũ rằng ViT5 phải bị loại do tokenizer không đọc `{` và `}`.

Lịch sử của các khái niệm này chỉ được giữ trong Git và `docs/archive/`, không
được đưa lại vào module runtime hoặc contract dữ liệu hiện hành.

## 4. Bản vá ViT5 bắt buộc

ViT5 gốc có tokenizer BPE cũ không tương thích trực tiếp với cách khởi tạo T5
tokenizer của Transformers mới và `{ } | =` rơi vào `<unk>`. Cách sửa đã được
thử nghiệm là đổi surface của bốn sentinel token, giữ nguyên ID và embedding:

```text
36095: <extra_id_0> → {
36094: <extra_id_1> → }
36093: <extra_id_2> → |
36092: <extra_id_3> → =
```

Không thêm token, không resize embedding và không đổi số tham số. Bản triển
khai chính thức phải pin revision nguồn, assert ID/vocab trước khi sửa, lưu
manifest và có test save/reload/round-trip. Chi tiết ở
`docs/MODEL_TOKENIZER_SPEC.md`.

## 5. Cổng hoàn thành

Project chỉ được coi đã chuyển sang kiến trúc mới khi:

1. ontology mới parse được và các query mẫu trả đúng dữ liệu;
2. runtime không import hoặc gọi QueryPlan/traversal cũ;
3. tokenizer của cả ba model round-trip toàn bộ target không `<unk>`;
4. mọi target dataset parse, chỉ đọc và thực thi được;
5. train/validation/test không rò semantic family;
6. cả ba model có bằng chứng tokenizer và pipeline học được trước khi mở test;
7. benchmark cuối báo cáo ít nhất parse rate, execution rate, answer exact,
   canonical query exact và kết quả theo register/query shape.

## 6. Quy tắc cập nhật quyết định

Một thay đổi đối với model, ontology contract, output schema hoặc benchmark
protocol phải được ghi tại đây cùng lý do trước khi sửa hàng loạt code/data.
Số liệu thí nghiệm không tự động trở thành quyết định kiến trúc.
