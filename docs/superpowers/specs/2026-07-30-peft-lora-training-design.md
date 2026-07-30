# Thiết kế huấn luyện PEFT LoRA

## Mục tiêu

Huấn luyện model production `google/t5gemma-2-270m-270m` bằng LoRA tiêu chuẩn,
giảm VRAM nhưng vẫn giữ pipeline seq2seq, benchmark và CTranslate2 hiện tại.
Giải pháp phải dùng API Hugging Face phổ biến, không cần training loop riêng.

## Quyết định

- Dùng `peft` trực tiếp cùng `transformers.Seq2SeqTrainer`.
- Không dùng Unsloth, TRL, QLoRA hoặc quantization trong lúc huấn luyện.
- Base model được nạp BF16/FP16/FP32 theo policy phần cứng hiện có và đóng băng.
- LoRA dùng `r=32`, `lora_alpha=64`, `lora_dropout=0`, `bias="none"` và
  `TaskType.SEQ_2_SEQ_LM`.
- Adapter chỉ gắn vào attention và MLP của text encoder/decoder T5Gemma2:
  `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`.
- Không gắn adapter vào SigLIP vision tower dù các lớp ở đó có cùng tên lá.
- Learning rate là `1e-4`; các thiết lập còn lại giữ nguyên: seed 42, effective
  batch 8, AdamW 8-bit, cosine scheduler, warmup 10%, dynamic padding,
  gradient checkpointing, không `torch.compile` và greedy decoding.

## Vòng đời checkpoint

Trainer lưu adapter ở các checkpoint validation. Khi cần mở lại checkpoint tốt
nhất, pipeline nạp base model pretrained rồi gắn adapter bằng
`PeftModel.from_pretrained`. Trước validation cuối, benchmark và lưu artifact,
adapter được `merge_and_unload()` thành một checkpoint Transformers độc lập.

Chỉ checkpoint đã merge được đặt tại thư mục `model/` và chuyển sang
CTranslate2. Runtime không phụ thuộc PEFT và không nạp base model cộng adapter
riêng rẽ.

## Báo cáo

`metrics.json` ghi rõ phương pháp `peft_lora`, cấu hình adapter, số tham số được
huấn luyện, tổng tham số base và việc artifact đã merge. Các metric chất lượng,
quy tắc chọn checkpoint và benchmark test không thay đổi.

## Xử lý lỗi

Huấn luyện dừng trước optimizer step nếu không tìm đủ target module hoặc phát
hiện target thuộc vision tower. Thiếu PEFT báo lỗi cài train extra. Output model
directory vẫn phải rỗng để tránh ghi đè artifact cũ.

## Kiểm thử

- Unit test khóa cấu hình LoRA và learning rate.
- Unit test target discovery chỉ chọn text encoder/decoder và từ chối danh sách
  rỗng.
- Test hiện có cho precision, padding, greedy decoding và dataset gate tiếp tục
  chạy nguyên vẹn.
- Smoke train T5Gemma2 local xác minh loss giảm, merge/reload sinh output tương
  đương và VRAM nằm trong 6 GB.

## Ngoài phạm vi

Không fine-tune chính thức, thay dataset/ontology, tuning rank hoặc learning
rate, benchmark test, convert artifact production hay sửa web runtime trong đợt
thay đổi code này.
