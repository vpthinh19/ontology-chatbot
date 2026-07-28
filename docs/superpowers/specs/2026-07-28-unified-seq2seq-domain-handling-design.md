# Một model thống nhất xử lý trong và ngoài miền

## Mục tiêu

Hệ thống production chỉ dùng một model seq2seq. Model vừa quyết định câu hỏi có
thể được trả lời bằng ontology hay không, vừa sinh SPARQL khi có thể trả lời.
PhoBERT domain gate, artifact gate và dataset gate được loại bỏ khỏi kiến trúc
đích.

Ontology, dataset và benchmark hiện có sẽ được xây lại từ tài liệu chính thức.
Không coi dữ liệu, artifact hoặc điểm benchmark hiện tại là kết quả cuối cùng
của thiết kế mới.

## Contract đầu ra model

Mỗi prediction sau khi bỏ khoảng trắng đầu/cuối phải thuộc đúng một trong hai
dạng:

```text
SELECT ...
```

hoặc marker từ chối cố định:

```text
không có thông tin
```

Marker dùng chữ thường, không dấu câu và phải round-trip qua tokenizer của
BARTpho, ViT5 và T5Gemma2. Không thêm prefix như `ANSWER`, `REJECT`, nhãn intent
hoặc JSON bao ngoài SPARQL.

## Luồng runtime

```text
câu hỏi
→ normalize_model_input
→ model seq2seq
→ "không có thông tin": trả "Không có thông tin."
→ SELECT: xác minh, thực thi RDFLib và render literal
→ query lỗi hoặc không có kết quả: trả "Không có thông tin."
```

Backend không fuzzy-match, sửa query, suy đoán IRI hoặc gọi model phân loại thứ
hai. Log vẫn ghi input chuẩn hoá, output nguyên văn, kết quả xác minh, số dòng
và thời gian xử lý.

## Ranh giới miền

Một câu thuộc miền khi ontology mới có đủ dữ liệu và danh mục SPARQL có truy
vấn trả lời trọn vẹn toàn bộ yêu cầu. Các trường hợp sau dùng marker từ chối:

- ngoài học vụ;
- gần học vụ nhưng ontology không chứa dữ liệu cần thiết;
- câu mơ hồ hoặc thiếu thông tin bắt buộc để chọn một câu trả lời đúng;
- chào hỏi, trò chuyện chung hoặc văn bản vô nghĩa;
- câu gồm nhiều yêu cầu mà có ít nhất một yêu cầu không được hỗ trợ.

Hệ thống không trả lời một phần câu hỗn hợp.

## Dataset hợp nhất

Chỉ còn `resources/dataset/main/{train,val,test}.jsonl`. Bản ghi vẫn có năm
trường `id`, `query_id`, `register`, `input`, `target`.

- Câu trong miền: `target` là một dòng SPARQL `SELECT` canonical có kết quả.
- Câu ngoài miền: `query_id` là `no-information`, `target` là
  `không có thông tin`.
- Các câu người dùng đã thử trong `resources/cases/user_queries.txt` phải được
  gán target theo ontology mới và đưa vào dataset hợp nhất.
- Câu hỗn hợp chỉ có target `không có thông tin`.

Positive và negative phải xuất hiện trong cả train, validation và test. Exact
duplicate sau preprocessing bị cấm giữa các split. Near-duplicate chỉ là lỗi
leakage khi hai câu thuộc cùng `query_id`; câu hỏi có cấu trúc giống nhau nhưng
tham chiếu hai thực thể hoặc hai truy vấn canonical khác nhau được báo cáo để
kiểm tra, không tự động loại bỏ.

## Huấn luyện và benchmark

Chỉ fine-tune và benchmark ba model:

- `vinai/bartpho-syllable`;
- `VietAI/vit5-base`;
- `google/t5gemma-2-270m-270m`.

Ba model dùng cùng split, normalizer, target marker, giao thức huấn luyện và
greedy decoding. Không benchmark PhoBERT và không huấn luyện classifier riêng.

Các số liệu phải được tách rõ:

- In-domain Answer Exact sau khi SPARQL được thực thi;
- tỷ lệ sinh chính xác marker trên câu ngoài miền;
- false acceptance: câu ngoài miền sinh thành SPARQL hợp lệ có kết quả;
- tỷ lệ từ chối đúng câu hỗn hợp;
- System Answer Exact sau toàn bộ backend, báo cáo theo in-domain,
  out-of-domain và tổng thể;
- parse rate, execution rate và Result F1 cho phần trong miền để chẩn đoán.

Không dùng một accuracy tổng hợp duy nhất để che chất lượng trả lời trong miền
hoặc chất lượng từ chối.

## Phạm vi cập nhật tài liệu

Khi đặc tả này được duyệt, đồng bộ `README.md`, `docs/CONCEPT.md`,
`docs/ARCHITECTURE.md`, `docs/DATASET.md`, `docs/TRAINING.md`,
`docs/EVALUATION.md`, `docs/DEPLOYMENT.md` và các đặc tả production còn hiệu
lực. Loại bỏ mô tả PhoBERT gate, dataset gate, artifact gate, threshold và các
điểm benchmark cũ khỏi tài liệu mô tả hệ thống đích.

Các số lượng dataset, thống kê ontology và điểm model chỉ được đưa trở lại tài
liệu sau khi ontology/dataset mới được tạo và báo cáo được sinh từ artifact
thật. Không để số liệu giả hoặc placeholder.
