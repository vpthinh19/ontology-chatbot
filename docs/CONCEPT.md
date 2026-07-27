# Concept: tiếng Việt → SPARQL → ontology

## Bài toán

Hệ thống dịch một câu hỏi tiếng Việt sang SPARQL có giám sát. Model được phép
học schema và canonical IRI của ontology; ontology mới là nơi lưu dữ liệu trả
lời. Vì vậy thay nội dung literal mà giữ nguyên schema không đòi hỏi train lại
model, còn đổi IRI hoặc quan hệ có thể đòi hỏi cập nhật dataset.

Ontology là đồ thị, không phải cây. Ví dụ email của đơn vị xử lý bảo lưu nằm
sau một đường nối:

```text
AcademicLeaveProcedure
  --handledBy--> StudentAffairsOffice
  --email------> "ctsv@ntu.edu.vn"
```

Model sinh đường đi đó bằng SPARQL:

```sparql
SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?node . ?node :email ?answer . }
```

## Luồng dữ liệu

```mermaid
flowchart LR
    Q["Văn bản tự nhiên"] --> N["NFC + khoảng trắng + viết tắt chắc nghĩa"]
    N --> M["BARTpho / ViT5 / T5Gemma2"]
    M --> S["Một dòng SPARQL SELECT"]
    S --> V["Parser + danh sách thao tác cấm"]
    V --> G["RDFLib query"]
    G --> R["list[dict]"]
    R --> T["Văn bản trả lời"]
```

Không có tầng tự sửa query. Query sai là lỗi model/dataset; query đúng nhưng dữ
liệu sai là lỗi ontology. Ranh giới này giúp hệ thống dễ giải thích và dễ kiểm
thử.

## Contract đầu ra

Model chỉ sinh phần `SELECT`, không sinh `PREFIX`. Backend gắn các prefix cố
định cho namespace project, RDF, RDFS, SKOS và XSD. Target nằm trên một dòng,
có khoảng trắng nhất quán và phải nêu rõ cột kết quả; `SELECT *` không hợp lệ.

Kết quả cuối chỉ là:

- `rdfs:label` nếu người dùng hỏi tên một thực thể;
- literal của datatype property như `content`, `condition`, `email` hay mức
  học phí;
- giá trị tổng hợp như `COUNT`.

Object property như `handledBy`, `hasDocument` hay `basedOnRegulation` chỉ tạo
đường đi giữa các node, không được trả thẳng về giao diện.

Ví dụ hướng dẫn tổng quát:

```sparql
SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }
```

Ví dụ tên đơn vị xử lý:

```sparql
SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?node . ?node rdfs:label ?answer . }
```

Ví dụ nhiều kết quả và phép tổng hợp:

```sparql
SELECT ?count ?answer WHERE { { SELECT (COUNT(DISTINCT ?node) AS ?count) WHERE { ?node a :AdministrativeOffice . } } ?item a :AdministrativeOffice . ?item rdfs:label ?answer . }
```

## Phạm vi

Project tập trung vào semantic parsing trên một ontology có schema ổn định.
RAG, cơ sở dữ liệu phẳng, hội thoại ngoài miền, router nhiều model và heuristic
fuzzy không thuộc pipeline cốt lõi. Chỉ thêm một tầng mới khi benchmark chứng
minh pipeline hiện tại không thể giải quyết nhu cầu đó.

Việc nhận biết câu hỏi ngoài ontology chưa thuộc contract hiện tại. Trước khi
hoàn thiện dataset phải chọn một trong hai hướng: giới hạn rõ hệ thống ở câu
hỏi trong miền, hoặc bổ sung một output từ chối và tập dữ liệu âm. Không được
tự thêm `NO_QUERY` nếu chưa thay đổi contract đầu ra và benchmark tương ứng.

## Contract tài liệu

`README.md` là tài liệu tiếng Việt đọc độc lập, có cấu trúc gần một báo cáo
nghiên cứu: bài toán, phương pháp, ontology, dataset, kiến trúc, thực nghiệm,
kết quả, hạn chế, tái lập và triển khai. Các file trong `docs/` là phụ lục kỹ
thuật, không phải nhật ký phát triển.

Thứ tự nội dung README đã chốt: tóm tắt; bài toán và đóng góp; tổng quan hệ
thống; ontology; dataset; model/tokenizer; fine-tuning; đánh giá; kết quả và
thảo luận; kiến trúc phần mềm; luồng dữ liệu runtime; cài đặt/tái lập; triển
khai; hạn chế, kết luận và tài liệu tham khảo. Phần kết quả chỉ được thêm khi có
benchmark mới hợp lệ, không để placeholder hoặc dùng lại điểm cũ.

- Sơ đồ kiến trúc, luồng dữ liệu và fine-tuning dùng Mermaid.
- Biểu đồ dataset và benchmark dùng SVG sinh từ JSON nguồn.
- Không ghi stage, phiên bản dataset/model hoặc kết quả benchmark đã hết hiệu
  lực.
- README chỉ công bố kết quả model sau khi cả ba model chạy cùng giao thức trên
  dataset đã qua toàn bộ cổng chất lượng.

`manifest.json` và `reports/dataset.json` là nguồn số liệu dataset;
`reports/models.json` chỉ được sinh từ đủ ba artifact hợp lệ. README và biểu đồ
không được giữ bản sao số liệu nhập tay trái với các nguồn này.
