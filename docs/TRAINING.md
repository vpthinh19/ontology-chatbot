# Huấn luyện

## So sánh công bằng

BARTpho, ViT5 và T5Gemma2 dùng cùng train/validation/test, normalizer, độ dài
tối đa, dynamic padding, greedy decoding và metric. Mỗi model chỉ khác những
thiết lập bắt buộc để chạy ổn định trong 6 GB VRAM, như batch vi mô, attention
backend và gradient checkpointing.

Thiết lập chung:

- BF16 và TF32;
- dynamic padding đến bội số 8;
- không dùng `torch.compile`;
- AdamW 8-bit;
- seed cố định để lần chạy có thể tái lập;
- chọn checkpoint theo `eval_answer_exact_rate`;
- test không tham gia chọn checkpoint.

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

## Lệnh chạy

```bash
uv sync --extra train --dev

uv run --extra train train_sparql \
  --model bartpho \
  --epochs 60 \
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
