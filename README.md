# NTU Ontology Chatbot

Chatbot tiếng Việt tra cứu thông tin học vụ trong ontology RDF. Hướng kiến
trúc đã chốt của project là:

```text
câu hỏi tiếng Việt
  → chuẩn hoá nhẹ
  → BARTpho hoặc ViT5
  → SPARQL SELECT
  → RDFLib thực thi trên ontology
  → label/literal trả cho người dùng
```

Model sinh trực tiếp SPARQL và được phép biết schema cùng canonical IRI của
ontology. Backend không có QueryPlan, cây vàng, fuzzy matching, thuật toán
traversal riêng hay lớp DTO kết quả theo kiến trúc cũ.

## Nguồn sự thật

Đọc tài liệu theo thứ tự sau:

1. [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md): quyết định đã chốt, phạm vi
   và các bất biến của kiến trúc.
2. [`docs/CONCEPT.md`](docs/CONCEPT.md): hình dạng khái niệm và luồng dữ liệu.
3. [`docs/DATASET_BENCHMARK_SPEC.md`](docs/DATASET_BENCHMARK_SPEC.md): cách tái
   sử dụng dữ liệu cũ, gán target SPARQL và đánh giá hai model.
4. [`docs/MODEL_TOKENIZER_SPEC.md`](docs/MODEL_TOKENIZER_SPEC.md): contract
   tokenizer có thể tái lập cho BARTpho và ViT5.
5. [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md): thứ tự thi
   công và điều kiện hoàn thành từng giai đoạn.

Nếu code, artifact hoặc tài liệu lịch sử mâu thuẫn với
`docs/PROJECT_SPEC.md`, đặc tả project được ưu tiên. Các quyết định mới phải
được cập nhật vào file đó trước khi triển khai rộng.

## Các quyết định chính

- Ontology canonical dùng Turtle, RDFLib và OWL-RL khi thực sự cần suy luận.
- `content` được giữ để trả lời câu hỏi yêu cầu hướng dẫn tổng quát.
- `Condition` và `Outcome` sẽ được làm phẳng thành datatype property lặp
  `condition` và `outcome`.
- Object property chỉ là đường nối. Kết quả cuối là `rdfs:label`, datatype
  literal hoặc giá trị tổng hợp SPARQL.
- Output model là một câu `SELECT` SPARQL canonical trên một dòng; backend tự
  thêm prefix cố định.
- Hai model nghiên cứu là `vinai/bartpho-syllable` và `VietAI/vit5-base`.
- Dynamic padding, BF16/TF32 và `torch.compile=False` trên RTX 4050 6 GB.
- Không dùng cơ sở dữ liệu phẳng làm baseline chính.
- Khoảng 1.000 câu hỏi cũ được tái sử dụng sau review; target QueryPlan cũ phải
  được gán lại thành SPARQL theo ontology mới.

## Trạng thái chuyển đổi

Repository đang ở giai đoạn chuyển từ prototype QueryPlan sang kiến trúc
SPARQL trực tiếp. Vì vậy một số code và dữ liệu cũ vẫn còn để làm nguồn chuyển
đổi, nhưng không còn là contract cần tiếp tục phát triển.

- [x] Chốt model, kiến trúc đích và nguyên tắc ontology.
- [x] Kiểm chứng BARTpho và ViT5 có thể học SPARQL ở phép thử nhỏ.
- [x] Xác định bản vá tokenizer ViT5 không đổi kích thước vocabulary.
- [x] Tạo và kiểm định ontology v11 từ `ontology_v10.ttl`.
- [x] Thay runtime QueryPlan bằng executor SPARQL tối giản.
- [x] Chuyển dataset cũ sang target SPARQL và bổ sung aggregate/filter có mục tiêu.
- [x] Xây dataset và benchmark SPARQL v1 độc lập.
- [ ] Train và chấm hai model chính thức với nhiều seed.

Không dùng kết quả validation QueryPlan trước đây làm kết quả cuối cho kiến
trúc SPARQL.
