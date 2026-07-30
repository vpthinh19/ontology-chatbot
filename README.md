# NTU Ontology Chatbot

Chatbot tiếng Việt trả lời câu hỏi học vụ bằng cách chuyển câu hỏi thành SPARQL
và truy vấn ontology RDF. Ontology và dataset được xây dựng từ các quyết định,
phụ lục và hướng dẫn chính thức của Trường Đại học Nha Trang.

## Trạng thái hiện tại

- **Đã kiểm chứng:** ontology canonical, semantic index, answer inventory,
  query catalogue và dataset hợp nhất 4.454 câu.
- **Dataset:** 3.645 câu train, 402 câu validation và 407 câu test; đủ 51 họ
  truy vấn, sáu miền nội dung và bốn phong cách diễn đạt.
- **Quy trình học vụ:** 142 target canonical đều có mặt trong ba split; train có
  2.128 câu `procedure-*`, mỗi target có ít nhất mười câu và đủ bốn phong cách.
- **Chưa thực hiện:** fine-tune và benchmark BARTpho, ViT5, T5Gemma2 trên
  dataset đang được khóa. Các chỉ số từ dataset trước không đại diện cho trạng
  thái hiện tại.

Chiều kiểm soát độ phủ bắt buộc là:

```text
ontology → inventory → catalogue → dataset
```

Catalogue gồm 51 họ truy vấn và phủ bằng máy toàn bộ 2.953 khả năng trả lời
`supported` trong inventory. Dataset sử dụng đủ 51 họ; mọi target trong miền
đều parse, qua contract an toàn, thực thi trên graph và trả về dữ liệu.

## Bài toán và phương pháp

Hệ thống dùng một model encoder-decoder cho hai nhiệm vụ gắn liền nhau:

1. từ chối câu hỏi mà ontology không thể trả lời trọn vẹn;
2. sinh một truy vấn SPARQL `SELECT` cho câu hỏi được hỗ trợ.

Model không chứa câu trả lời học vụ. Nội dung hướng dẫn, nhãn thực thể, email,
địa điểm, mức học phí và các literal khác nằm trong ontology và chỉ được lấy ra
khi backend thực thi SPARQL.

```mermaid
flowchart LR
    Q["Câu hỏi tiếng Việt"] --> N["Chuẩn hoá nhẹ"]
    N --> M["Model seq2seq"]
    M --> D{"Output"}
    D -- "không có thông tin" --> X["Không có thông tin."]
    D -- "SELECT ..." --> V["Xác minh SPARQL"]
    V -- "không hợp lệ" --> X
    V -- "hợp lệ" --> O["RDFLib + ontology"]
    O -- "không có kết quả" --> X
    O -- "literal" --> R["Định dạng câu trả lời"]
```

Không có model phân loại thứ hai, fuzzy matching, tự sửa query hoặc logic dò IRI
trong backend.

## Ranh giới trong và ngoài miền

Output model chỉ có hai dạng:

```text
SELECT ?answer WHERE { ... }
```

```text
không có thông tin
```

Câu ngoài học vụ, câu gần học vụ nhưng ontology thiếu dữ liệu, câu mơ hồ và câu
trộn nhiều yêu cầu mà có ít nhất một phần không được hỗ trợ đều dùng marker từ
chối. Hệ thống không trả lời một phần câu hỗn hợp.

## Ontology

Nguồn công văn chính thức quyết định dữ liệu và phạm vi trả lời. Ontology dùng
IRI tiếng Anh ổn định, `rdfs:label@vi` cho tên tiếng Việt chính và
`skos:altLabel@vi` cho tên gọi thay thế hữu ích. Object property tạo đường đi
trên graph; label và datatype property là dữ liệu được trả về.

Lớp văn bản nguồn, học phí, biểu mẫu và các bảng quy tắc đã được đối chiếu với
`NTUdocs`. Ontology canonical hiện có 22 quy trình, 2 chính sách và inventory
máy đọc được tại `resources/ontology/answer_inventory.json`. Các chủ đề nghỉ
ốm, học liên thông, cảnh báo và buộc thôi học đã có đường truy vấn về đúng
provision nguồn.

Chi tiết nằm tại [docs/ONTOLOGY.md](docs/ONTOLOGY.md).

## Dataset

Dataset hợp nhất nằm tại `resources/dataset/main/` và có 4.454 câu: 3.645 train,
402 validation, 407 test. Trong đó 3.627 câu thuộc năm miền trả lời được
(quy trình, học phí, quy tắc học vụ, chứng chỉ, biểu mẫu) và 827 câu ngoài miền
dùng marker `không có thông tin`. Bốn phong cách `formal`, `neutral`,
`colloquial`, `noisy` lần lượt có 1.016, 1.153, 1.075 và 1.210 câu.

Train dạy toàn bộ schema và giá trị slot hữu hạn. Validation dùng cách diễn đạt
chưa thấy để chọn checkpoint; test được đóng băng và chỉ dùng cho đánh giá cuối.
Mọi họ truy vấn đều có mặt trong cả ba split, nhưng câu hỏi đã chuẩn hóa và câu
gần trùng cùng họ không được đi xuyên split.

![Phân bố train, validation và test](reports/figures/dataset-splits.svg)

![Phân bố phong cách câu hỏi](reports/figures/registers.svg)

Phân bố cùng checksum được sinh trong `resources/dataset/main/manifest.json`
và `reports/dataset.json`; contract riêng cho 142 target quy trình nằm trong
`reports/procedure-dataset.json`. Các câu người dùng thực tế được giữ tại
`resources/cases/user_queries.txt`; cả bảy câu đều xuất hiện đúng một lần trong
test để giữ vai trò hồi quy người dùng.

Ngoài test đã khóa, `resources/cases/procedure_language.jsonl` có 308 câu chấp
nhận production (220 câu quy trình và 88 câu phải từ chối). Bộ này dùng để bắt
lỗi hồi quy ngôn ngữ cơ bản sau huấn luyện, không được xem là benchmark khoa
học độc lập hay dùng để chọn checkpoint.

Chi tiết nằm tại [docs/DATASET.md](docs/DATASET.md).

## Mô hình và đánh giá

Ba model encoder-decoder được benchmark trên cùng dataset và giao thức là
`vinai/bartpho-syllable`, `VietAI/vit5-base` và
`google/t5gemma-2-270m-270m`. Kết quả test quyết định checkpoint duy nhất được
đưa vào runtime.

Mỗi model được huấn luyện bằng PEFT LoRA trên attention và FFN tương ứng của
encoder/decoder. Base pretrained được đóng băng trong lúc train; adapter tốt
nhất được merge thành một checkpoint Transformers độc lập trước khi benchmark
và chuyển sang CTranslate2. Runtime vì vậy vẫn chỉ nạp một model, không phụ
thuộc PEFT.

Metric chính trong miền là Answer Exact sau khi thực thi SPARQL. Phần ngoài
miền đo tỷ lệ sinh đúng marker, false acceptance và khả năng từ chối câu hỗn
hợp. System Answer Exact được báo cáo riêng cho trong miền, ngoài miền và toàn
bộ test. Chỉ công bố số liệu sau khi checkpoint được chọn bằng validation và
chạy đúng một lần trên test đã khóa.

Giao thức nằm tại [docs/TRAINING.md](docs/TRAINING.md) và định nghĩa metric nằm
tại [docs/EVALUATION.md](docs/EVALUATION.md).

## Kiến trúc phần mềm

```text
resources/
├── ontology/ontology.ttl
├── cases/user_queries.txt
└── dataset/main/
src/ontchatbot/
├── runtime/      # inference, SPARQL, RDFLib, renderer và API
├── research/     # dataset, fine-tuning, benchmark và báo cáo
├── tools/        # tokenizer và chuyển đổi artifact
├── cli/          # entry point dòng lệnh
└── settings.py
docs/             # concept và đặc tả kỹ thuật
reports/          # JSON nguồn và biểu đồ được sinh lại
tests/            # kiểm tra theo package
```

Runtime production chỉ cần một artifact seq2seq đã chuyển đổi, tokenizer,
RDFLib và ontology. Thiết kế module chi tiết nằm tại
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); contract triển khai nằm tại
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Tái lập nghiên cứu

Trình tự tái lập là: xây ontology từ tài liệu chính thức, audit semantic index,
lập inventory khả năng trả lời, lập catalogue SPARQL có kết quả, xác minh
dataset hợp nhất, kiểm tra tokenizer, fine-tune model theo giao thức đã khóa,
benchmark checkpoint được chọn và sinh báo cáo từ JSON máy đọc.

Không giữ số liệu giả, không tái sử dụng benchmark hết hiệu lực và không dùng
test để chọn checkpoint.
