# Huấn luyện

## Trạng thái

Ontology, catalogue và dataset 3.558 câu đã vượt các cổng kiểm tra tĩnh.
T5Gemma2 chưa được fine-tune trên dữ liệu đang khóa; vì vậy
chưa có benchmark chính thức cho trạng thái này. Chỉ số và checkpoint tạo từ dataset
khác không được dùng để mô tả chất lượng hiện tại.

## Giao thức huấn luyện

Model được nghiệm thu là T5Gemma2. Trainer, benchmark và runtime dùng cùng
normalizer, target marker, độ dài tối đa, dynamic padding và greedy decoding.

Thiết lập chung đã chốt:

- seed `42`, đúng một lần chạy;
- effective batch size `8`;
- PEFT LoRA BF16 với rank `32`, alpha `64`, dropout `0` và bias `none`;
- learning rate `1e-4`, AdamW 8-bit, weight decay `0.005`;
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

Giữ nguyên dropout của checkpoint. T5Gemma2 dùng microbatch 4, gradient
accumulation 2, SDPA và gradient checkpointing để giữ effective batch bằng 8
trong 6 GB VRAM.

LoRA chỉ gắn vào `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`,
`up_proj` và `down_proj` thuộc text encoder/decoder. Vision tower SigLIP không
tham gia huấn luyện. Cấu hình này cập nhật 15.187.968 tham số, khoảng 1,9% model;
không dùng Unsloth, TRL hoặc QLoRA.

Dataset hợp nhất có thêm câu ngoài miền nên số optimizer step tăng theo số bản
ghi thật. Không giảm dữ liệu hoặc đổi epoch riêng cho một model để rút ngắn
benchmark.

## Tokenizer

Hai target output là một dòng SPARQL hoặc `không có thông tin`. Tokenizer của
T5Gemma2 phải round-trip marker và toàn bộ target trước khi trainer chạy; không
sửa vocabulary.

## Chọn checkpoint

Checkpoint trung gian chứa adapter PEFT. Khi validation chọn được checkpoint
tốt nhất, pipeline nạp lại adapter trên base pretrained rồi gọi
`merge_and_unload()`. Validation cuối, benchmark và thư mục `model/` đều dùng
checkpoint Transformers đã merge; runtime và CTranslate2 không nạp adapter
riêng.

Validation phải báo cáo riêng:

- In-domain Answer Exact;
- exact marker ngoài miền;
- false acceptance;
- từ chối câu hỗn hợp;
- System Answer Exact.

Tiêu chí chọn checkpoint được cố định trước lần train. Test chỉ chạy sau khi
checkpoint được chọn. Không dò
hyperparameter, không chạy nhiều seed và không tự train lại vì điểm test thấp.

## Trình tự chạy

1. Khóa ontology semantic index và inventory khả năng trả lời.
2. Xác minh catalogue phủ inventory.
3. Xác minh checksum dataset hợp nhất và tokenizer.
4. Fine-tune T5Gemma2 đúng một lần và chọn checkpoint bằng validation.
5. Mở lại checkpoint bằng `from_pretrained()` để benchmark test đã khóa.
6. Chỉ chuyển checkpoint được chấp nhận sang CTranslate2 khi cần triển khai.

Lệnh đã dùng trên RTX 4050 6 GB:

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True uv run train_sparql \
  --model t5gemma2 \
  --output-dir artifacts/procedure-recovery \
  --epochs 20 \
  --seed 42 \
  --save-model \
  --benchmark-after-training \
  --local-files-only
```

Biến allocator chỉ tránh phân mảnh VRAM, không thay đổi hyperparameter hoặc dữ
liệu. CLI và runtime đều dùng một model; không có artifact phân loại thứ hai.
