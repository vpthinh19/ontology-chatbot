# Huấn luyện

## Trạng thái

Ontology, catalogue và dataset 3.558 câu đã vượt các cổng kiểm tra tĩnh.
Ba model chưa được fine-tune trên dữ liệu đang khóa; vì vậy
chưa có benchmark chính thức cho trạng thái này. Chỉ số và checkpoint tạo từ dataset
khác không được dùng để mô tả chất lượng hiện tại.

## Giao thức huấn luyện

Ba model được benchmark là BARTpho-syllable, ViT5-base và T5Gemma2. Trainer và
benchmark dùng cùng normalizer, target marker, độ dài tối đa, dynamic padding,
giao thức LoRA và greedy decoding. Runtime chỉ triển khai một checkpoint được
chọn sau benchmark.

Thiết lập chung đã chốt:

- seed `42`, đúng một lần chạy;
- physical và effective batch size đều là `8`, không gradient accumulation;
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

Giữ nguyên dropout của từng checkpoint. Cả ba model dùng physical batch `8`,
gradient accumulation `1` và không gradient checkpointing. BARTpho và
T5Gemma2 dùng SDPA; ViT5 dùng eager attention. Smoke test PEFT trên RTX 4050
6 GB đã xác minh cả ba cấu hình chạy được; T5Gemma2 phải được smoke lại trên
batch dài nhất sau khi khóa dataset cuối vì có biên VRAM hẹp nhất.

LoRA gắn vào các vai trò tương đương, không ép dùng chung tên module:

| Model | Attention | FFN |
|---|---|---|
| BARTpho | `q_proj`, `k_proj`, `v_proj`, `out_proj` | `fc1`, `fc2` |
| ViT5 | `q`, `k`, `v`, `o` | `wi`, `wo` |
| T5Gemma2 | `q_proj`, `k_proj`, `v_proj`, `o_proj` | `gate_proj`, `up_proj`, `down_proj` |

T5Gemma2 loại trừ hoàn toàn vision tower SigLIP. Không dùng Unsloth, TRL hoặc
QLoRA.

Dataset hợp nhất có thêm câu ngoài miền nên số optimizer step tăng theo số bản
ghi thật. Không giảm dữ liệu hoặc đổi epoch riêng cho một model để rút ngắn
benchmark.

## Tokenizer

Hai target output là một dòng SPARQL hoặc `không có thông tin`. Tokenizer của
từng model phải round-trip marker và toàn bộ target trước khi
trainer chạy. ViT5 dùng tokenizer repair tái tạo được đã đặc tả; hai model còn
lại không sửa vocabulary.

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
4. Fine-tune mỗi model đúng một lần và chọn checkpoint riêng bằng validation.
5. Mở lại ba checkpoint bằng `from_pretrained()` để benchmark cùng test đã khóa.
6. Chọn một model theo kết quả đã công bố và chuyển checkpoint đó sang
   CTranslate2 khi cần triển khai.

Mẫu lệnh cho RTX 4050 6 GB:

```bash
for model in bartpho vit5 t5gemma2; do
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True uv run train_sparql \
    --model "$model" \
    --output-dir artifacts/model-benchmark \
    --epochs 20 \
    --seed 42 \
    --save-model \
    --benchmark-after-training \
    --local-files-only || break
done
```

Biến allocator chỉ tránh phân mảnh VRAM, không thay đổi hyperparameter hoặc dữ
liệu. Trainer tạo ba candidate độc lập; runtime cuối cùng chỉ dùng một model và
không có artifact phân loại thứ hai.
