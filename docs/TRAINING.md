# Huấn luyện

## So sánh công bằng

BARTpho, ViT5 và T5Gemma2 dùng cùng train/validation/test, normalizer, độ dài
tối đa, dynamic padding, greedy decoding và metric. Mỗi model chỉ khác những
thiết lập bắt buộc để chạy ổn định trong 6 GB VRAM, như batch vi mô, attention
backend và gradient checkpointing.

Thiết lập chung đã chốt:

- seed `42`, đúng một lần chạy cho mỗi model;
- effective batch size `8`;
- learning rate `3e-5`, AdamW 8-bit, weight decay `0.005`;
- cosine scheduler với `warmup_steps=0.1` (10% tổng optimizer step);
- tối đa 20 epoch, validation mỗi 2 epoch;
- dừng sớm sau ba mốc validation liên tiếp không cải thiện;
- dynamic padding đến bội số 8;
- không dùng `torch.compile`;
- greedy decoding (`num_beams=1`, `do_sample=False`);
- chọn checkpoint theo `eval_answer_exact_rate`;
- test không tham gia chọn checkpoint.

Mixed precision được chọn từ môi trường thay vì bật cứng: CUDA có BF16 dùng
BF16; CUDA không có BF16 dùng FP16; CPU dùng FP32. TF32 chỉ bật trên GPU CUDA
có compute capability từ 8 trở lên. Trên RTX 4050, giao thức dùng BF16 và TF32.

Giữ nguyên dropout của checkpoint: BARTpho `0.1`, ViT5 `0.1`, T5Gemma2 `0.0`.
Không tắt hoặc ép dropout riêng cho model nào. Batch vi mô có thể khác để vừa
6 GB VRAM nhưng tích lũy gradient phải giữ effective batch bằng 8. Attention
backend và gradient checkpointing chỉ được khác khi kiến trúc/bộ nhớ yêu cầu.

| Model | Microbatch | Gradient accumulation | Effective batch | Attention | Gradient checkpointing |
|---|---:|---:|---:|---|---|
| BARTpho | 4 | 2 | 8 | SDPA | Không |
| ViT5 | 8 | 1 | 8 | Eager | Không |
| T5Gemma2 | 4 | 2 | 8 | SDPA | Có |

Seed và các chi tiết tương thích tokenizer được ghi trong metric artifact để
tái lập, nhưng không phải tiêu chí xếp hạng model.

## Tokenizer

BARTpho cần khoảng trắng canonical trong SPARQL và không chấp nhận một số tên
biến tùy ý. Dataset chỉ dùng tên biến round-trip chính xác.

Tokenizer đóng gói của ViT5 có bốn ký hiệu cấu trúc bị chiếm bởi sentinel. Công
cụ `prepare_vit5_tokenizer` đổi tên đúng bốn entry đó sang `{`, `}`, `|`, `=`
nhưng giữ nguyên ID, kích thước vocabulary và tokenization tiếng Việt. Manifest
checksum khiến thao tác này tái tạo được.

T5Gemma2 dùng regex tokenizer tương thích với checkpoint gốc. Cả ba tokenizer
đều phải qua kiểm tra toàn bộ target trước khi trainer chạy.

BARTpho và T5Gemma2 không sửa vocabulary. ViT5 là model duy nhất được chuẩn bị
lại tokenizer; thao tác đổi bốn entry phải tái tạo được từ checkpoint gốc và
không làm thay đổi tokenization tiếng Việt.

## Lệnh chạy

```bash
uv sync --extra train --dev

uv run --extra train train_sparql \
  --model bartpho \
  --epochs 20 \
  --save-model \
  --benchmark-after-training \
  --local-files-only
```

Chạy tương tự với `--model vit5` và `--model t5gemma2`. Artifact được đặt dưới
`artifacts/models/<model>/`; không gắn số phiên bản dataset/model vào tên.

Trainer ghi `training_log` gồm train loss theo bước và metric validation tại
mỗi lần đánh giá. Train loss cho biết model có học được tín hiệu hay không;
validation answer exact mới là tiêu chí chọn checkpoint. Test metric chỉ mô tả
khả năng tổng quát hóa cuối cùng.

Lệnh trên chỉ được dùng sau khi dataset qua audit trong `docs/DATASET.md`. Không
dò hyperparameter, không chạy nhiều seed và không tự khởi động lại một model
nếu chưa có phê duyệt.
