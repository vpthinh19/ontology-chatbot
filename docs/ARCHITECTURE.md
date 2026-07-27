# Kiến trúc hệ thống

## Thành phần

```mermaid
flowchart TB
    UI["Web / API client"] --> API["runtime/api.py"]
    API --> P["OntologyChatbot"]
    P --> G["QueryGenerator"]
    G --> CT2["CTranslate2 model"]
    P --> Q["SPARQL validator + executor"]
    Q --> RDF["ontology.ttl"]
    P --> R["Generic renderer"]
    R --> UI

    D["train / val / test"] --> TR["research/training.py"]
    TR --> HF["Checkpoint Hugging Face tốt nhất"]
    HF --> BM["Benchmark Transformers"]
    HF --> CV["tools/conversion.py"]
    CV --> CT2
    CT2 --> PA["Kiểm tra parity + hiệu năng"]
```

Runtime chỉ phụ thuộc model đã chuyển đổi, tokenizer, RDFLib và ontology. Nó
không import trainer, dataset curation hay code báo cáo.

## Trách nhiệm

| Thành phần | Nhận | Trả | Không làm |
|---|---|---|---|
| Normalizer | Câu hỏi | Văn bản sạch nhẹ | Dò entity, sinh IRI |
| Model | Văn bản | SPARQL | Đọc literal trong ontology |
| Validator | SPARQL | SPARQL an toàn | Sửa query |
| RDFLib | SPARQL + graph | Các literal | Suy đoán ý người dùng |
| Renderer | `list[dict]` | Văn bản | Chứa logic riêng cho ontology |

`runtime/pipeline.py` là điểm đọc ngắn nhất để hiểu luồng chạy thật.
`research/training.py` là điểm bắt đầu cho huấn luyện; `research/evaluation.py`
định nghĩa metric dùng chung cho validation và test.

## Vòng đời model

Ba model dùng cùng interface cấp cao của Transformers:

```text
AutoTokenizer → AutoModelForSeq2SeqLM → Seq2SeqTrainer
              → checkpoint → from_pretrained() → generate()
```

Checkpoint Hugging Face được mở lại bằng `from_pretrained()` trong một tiến
trình đánh giá độc lập và là nguồn điểm chất lượng chính. Chính checkpoint đó
được chuyển sang CTranslate2. CTranslate2 chỉ dùng để kiểm tra parity, tốc độ
và tài nguyên triển khai; sai khác sau conversion không được quy thành năng lực
của pretrained model. Không có model lai hoặc trạng thái model đặc biệt trong
RAM.

## An toàn truy vấn

Backend chỉ chấp nhận `SELECT`, cấm `SELECT *`, truy vấn liên kết ngoài và mọi
thao tác thay đổi graph. Kết quả tối đa 100 dòng. URI hoặc blank node lọt ra
kết quả bị xem là vi phạm contract: target phải project label hoặc literal.

## Dạng dữ liệu nội bộ

Không có hierarchy DTO. Sau RDFLib, dữ liệu chỉ còn:

```python
list[dict[str, str | int | float | bool | None]]
```

Nhờ vậy query một cột, nhiều cột, danh sách và kết quả tổng hợp cùng đi qua một
renderer.
