# Huấn luyện

## Trạng thái

Ontology, catalogue và dataset 2.150 câu đã vượt các cổng readiness. Dataset đã
được khóa bằng checksum nên có thể dùng cho fine-tuning theo giao thức dưới đây.
Hiện chưa có benchmark chính thức trên release này; mọi kết quả thử nghiệm từ
dataset trước đó đều hết hiệu lực.

## So sánh công bằng

BARTpho, ViT5 và T5Gemma2 dùng cùng train/validation/test, normalizer, target
marker, độ dài tối đa, dynamic padding, greedy decoding và metric. Không có
model phân loại hoặc quá trình huấn luyện thứ tư.

Thiết lập chung đã chốt:

- seed `42`, đúng một lần chạy cho mỗi model;
- effective batch size `8`;
- learning rate `3e-5`, AdamW 8-bit, weight decay `0.005`;
- cosine scheduler với `warmup_steps=0.1`;
- tối đa 20 epoch, validation mỗi 2 epoch;
- dừng sớm sau ba mốc validation liên tiếp không cải thiện;
- dynamic padding đến bội số 8;
- không dùng `torch.compile`;
- greedy decoding (`num_beams=1`, `do_sample=False`);
- test không tham gia chọn checkpoint.

Mixed precision được chọn theo môi trường: CUDA có BF16 dùng BF16; CUDA không
có BF16 dùng FP16; CPU dùng FP32. TF32 chỉ bật trên GPU CUDA có compute
capability từ 8 trở lên.

Giữ nguyên dropout của checkpoint. Batch vi mô, attention backend và gradient
checkpointing được phép khác để từng kiến trúc chạy ổn định trong 6 GB VRAM,
nhưng gradient accumulation phải giữ effective batch bằng 8.

| Model | Microbatch | Gradient accumulation | Attention | Gradient checkpointing |
|---|---:|---:|---|---|
| BARTpho | 4 | 2 | SDPA | Không |
| ViT5 | 8 | 1 | Eager | Không |
| T5Gemma2 | 4 | 2 | SDPA | Có |

Dataset hợp nhất có thêm câu ngoài miền nên số optimizer step tăng theo số bản
ghi thật. Không giảm dữ liệu hoặc đổi epoch riêng cho một model để rút ngắn
benchmark.

## Tokenizer

Hai target output là một dòng SPARQL hoặc `không có thông tin`. Cả ba tokenizer
phải round-trip marker và toàn bộ target trước khi trainer chạy.

BARTpho cần khoảng trắng canonical trong SPARQL. ViT5 dùng tokenizer đã chuẩn
bị lại bốn ký hiệu cấu trúc nhưng giữ nguyên ID/vocabulary. T5Gemma2 dùng regex
tokenizer tương thích checkpoint gốc. BARTpho và T5Gemma2 không sửa vocabulary.

## Chọn checkpoint

Validation phải báo cáo riêng:

- In-domain Answer Exact;
- exact marker ngoài miền;
- false acceptance;
- từ chối câu hỗn hợp;
- System Answer Exact.

Tiêu chí chọn checkpoint được cố định trước lần train đầu và áp dụng giống nhau
cho ba model. Test chỉ chạy sau khi checkpoint được chọn. Không dò
hyperparameter, không chạy nhiều seed và không tự train lại vì điểm test thấp.

## Trình tự chạy

1. Khóa ontology semantic index và inventory khả năng trả lời.
2. Xác minh catalogue phủ inventory.
3. Xác minh checksum dataset hợp nhất và tokenizer.
4. Fine-tune T5Gemma2 một lần để nghiệm thu khả năng học contract mới.
5. Khi pipeline hợp lệ, fine-tune BARTpho và ViT5 cùng giao thức.
6. Mở lại từng checkpoint bằng `from_pretrained()` để benchmark.
7. Chuyển cùng checkpoint sang CTranslate2 và kiểm tra parity triển khai.

Câu lệnh chính thức chỉ được ghi sau khi CLI được refactor sang dataset và
runtime một model; tài liệu không công bố lệnh cũ yêu cầu artifact thứ hai.
