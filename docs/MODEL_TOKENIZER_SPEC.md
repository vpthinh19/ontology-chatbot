# Đặc tả model và tokenizer

## 1. Model chính thức

| Model | Vai trò |
|---|---|
| `vinai/bartpho-syllable` | BART pretrained chuyên tiếng Việt |
| `VietAI/vit5-base` | T5 pretrained tiếng Việt, dùng tokenizer đã sửa có kiểm chứng |

T5Gemma và mBART không thuộc benchmark chính. Artifact cũ của chúng chỉ là
lịch sử thử nghiệm.

## 2. Contract target chung

Hai model nhận cùng input đã chuẩn hóa và cùng chuỗi target SPARQL canonical:

```sparql
SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }
```

Khoảng trắng trong target là nội dung chuỗi, khác với padding batch. Dùng một
khoảng trắng quanh `{`, `}`, `.`, toán tử và các thành phần SPARQL để tokenizer
ổn định. Training dùng dynamic padding theo batch, không pad toàn dataset về
một độ dài cố định.

Tập con target chung không dùng `_`, `^`, `<` hoặc `@`: `_` là unknown của
BARTpho, còn ba ký hiệu sau là unknown của ViT5. Chúng không cần thiết cho
ontology hiện tại. Literal có datatype/language được so sánh qua `STR`, ví dụ
`FILTER ( STR ( ?cohort ) = "K63" )`, thay vì sinh `^^xsd:string` hoặc `@vi`.
Full IRI cũng không xuất hiện vì backend cung cấp prefix cố định.

## 3. BARTpho

BARTpho nhạy với chuỗi ký hiệu dính liền. Target không dùng dạng
`WHERE{...}`. Validator tokenizer phải kiểm tra tất cả target:

- token cấu trúc không trở thành `<unk>`;
- decode giữ đủ ký hiệu cần để SPARQL parse được;
- cùng canonicalizer được dùng cho train và inference.

Không cần sửa vocabulary BARTpho theo kết quả hiện tại.

## 4. ViT5

### Vấn đề gốc

Checkpoint ViT5 dùng SentencePiece BPE và được tạo với Transformers cũ. Với
Transformers mới, các lớp T5 tokenizer có thể cố dựng tokenizer Unigram từ
vocabulary BPE và lỗi. Tokenizer gốc cũng ánh xạ `{`, `}`, `|`, `=` về ID
`<unk>` dù `EncodeAsPieces()` có thể hiển thị bề mặt ký tự.

### Bản sửa đã chọn

Dùng tokenizer backend BPE của checkpoint và đổi surface bốn sentinel token,
giữ nguyên ID:

| ID | Cũ | Mới |
|---:|---|---|
| 36095 | `<extra_id_0>` | `{` |
| 36094 | `<extra_id_1>` | `}` |
| 36093 | `<extra_id_2>` | `|` |
| 36092 | `<extra_id_3>` | `=` |

Đồng thời bỏ bốn sentinel đó khỏi `additional_special_tokens` để decode không
loại ký hiệu mới.

Bản sửa không:

- thêm token;
- thay ID token còn lại;
- resize embedding;
- đổi số tham số;
- thay tokenization của 344 input tiếng Việt đã kiểm tra.

### Yêu cầu tái lập

Script chính thức phải:

1. pin model revision
   `2209a38d735ede63e88f5aa52bcdc11a05a37b85`;
2. assert vocabulary size là 36096 và bốn ID nguồn đúng như bảng;
3. thực hiện mapping xác định, không tìm token theo phỏng đoán;
4. lưu tokenizer bằng định dạng mà `AutoTokenizer` có thể reload;
5. ghi manifest gồm model ID, revision, mapping và checksum file đầu ra;
6. kiểm tra encode/decode `{ } | =`, tiếng Việt và một tập SPARQL mẫu;
7. kiểm tra save/reload cho kết quả ID giống hệt;
8. không gọi `resize_token_embeddings()`.

## 5. Bằng chứng learning audit hiện tại

Trainer chính thức đã được chạy thật trên GPU với 16 target khác nhau, phủ lấy
literal trực tiếp, đi qua object property, nhiều cột, `FILTER` và `COUNT`.
Mỗi model học chính 16 câu đó trong 500 optimizer step, seed 42, LR `3e-5`,
BF16, TF32, dynamic padding bội số 8 và không compile:

| Model | Parse | Execute | Answer exact | Canonical exact | Thời gian | VRAM cấp phát cực đại |
|---|---:|---:|---:|---:|---:|---:|
| BARTpho | 16/16 | 16/16 | 16/16 | 16/16 | 130,686 giây | 3.172 MB |
| ViT5 | 16/16 | 16/16 | 15/16 | 15/16 | 84,682 giây | 2.491 MB |

Sai khác duy nhất của ViT5 là bỏ một triple `:condition` trong query ba cột;
query vẫn parse và thực thi. Vì vậy đây là lỗi học trên một audit nhỏ, không
phải lỗi tokenizer hay runtime.

Phép thử chỉ chứng minh cả tokenizer, collator, label masking, model và bộ sinh
đều hoạt động đầu-cuối; nó cố ý cho model thấy lại 16 câu và không phải
benchmark tổng quát hóa. Lệnh tái lập:

```bash
uv run --extra train train_sparql --model bartpho --learning-audit --max-steps 500 --local-files-only --output-dir artifacts/sparql_learning_audit_v1
uv run --extra train train_sparql --model vit5 --learning-audit --max-steps 500 --local-files-only --output-dir artifacts/sparql_learning_audit_v1
```

Kết luận cũ “loại ViT5” dựa trên cách thêm bốn token mới và resize embedding
đã bị thay thế bởi bản sửa sentinel này.

Tokenizer đã sửa cũng cho phép CTranslate2 convert checkpoint. CTranslate2 có
thể chạy CPU và không yêu cầu CUDA; CUDA chỉ cần nếu chọn inference GPU.

## 6. Cấu hình train chung

- Dynamic padding, ưu tiên bội số 8 khi phù hợp.
- BF16 và TF32.
- `torch.compile=False` vì lợi ích không bù rủi ro với độ dài động trên máy
  hiện tại.
- Đánh giá generation ở `batch_size=1` cho báo cáo cuối.
- Chọn checkpoint bằng validation generation cùng `batch_size=1`; không dùng
  metric sinh theo batch lớn rồi báo cáo theo batch 1.
- Không ép cùng learning rate/dropout nếu validation cho thấy optimum khác;
  tính công bằng nằm ở dữ liệu, target, split, budget đánh giá và cách chấm.

## 7. Thí nghiệm chính thức

Hai model đã được train 60 epoch với seed 7, 21 và 42. Trên benchmark độc lập,
ViT5 đạt trung bình 78,05% answer exact, BARTpho đạt 75,00%; parse/execute lần
lượt là 100,00% và 99,59%. Kết quả đầy đủ theo seed, register, query shape,
thời gian và VRAM nằm tại `SPARQL_EXPERIMENT_V1.md`.
