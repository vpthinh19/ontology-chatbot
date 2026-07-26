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

## 5. Bằng chứng thí nghiệm hiện có

Learning audit ViT5 với bản sửa sentinel dùng 18 câu train và 6 câu noisy giữ
riêng, 500 optimizer step, LR `3e-5`, batch vật lý 2, gradient accumulation 4,
BF16 và không compile:

| Seed | Train exact | Holdout parse | Holdout answer |
|---:|---:|---:|---:|
| 42 | 18/18 | 6/6 | 5/6 |
| 7 | 18/18 | 5/6 | 3/6 |
| 21 | 18/18 | 6/6 | 5/6 |

Phép thử chứng minh tokenizer/model có thể học SPARQL, không phải benchmark
tổng quát hóa. Kết luận cũ “loại ViT5” dựa trên cách thêm bốn token mới và
resize embedding đã bị thay thế bởi bản sửa sentinel này.

Tokenizer đã sửa cũng cho phép CTranslate2 convert checkpoint. CTranslate2 có
thể chạy CPU và không yêu cầu CUDA; CUDA chỉ cần nếu chọn inference GPU.

## 6. Cấu hình train chung

- Dynamic padding, ưu tiên bội số 8 khi phù hợp.
- BF16 và TF32.
- `torch.compile=False` vì lợi ích không bù rủi ro với độ dài động trên máy
  hiện tại.
- Đánh giá generation ở `batch_size=1` cho báo cáo cuối.
- Không ép cùng learning rate/dropout nếu validation cho thấy optimum khác;
  tính công bằng nằm ở dữ liệu, target, split, budget đánh giá và cách chấm.
