# AOTInductor: T5Gemma2 bfloat16

120 câu đúng ID lượt trước; greedy, batch 1, 320 token tối đa; warm-up tách khỏi 120 lần đo; p95 nearest-rank.

| cấu hình | đúng target | giống torch compile | median ms | p95 ms | nạp .so ms | gọi đầu ms | build .so s | .so MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CT2 cpu int8 | 99/120 (82,5%) | — | 1.741 | — | — | — | — | — |
| torch compile | 99/120 (82,5%) | 120/120 | 784 | 878 | — | 48.968 | — | — |
| AOTInductor (encoder) | chưa đo | — | — | — | — | — | — | — |

## Phạm vi AOTI

Chỉ text encoder là graph AOTI với chiều dài động 1–32768; decoder tự hồi quy, LM head và KV cache động còn eager. Build là export + compile/package, không gồm nạp model.
Không chạy full generation nếu bỏ `transformers`; package `.pt2` chứa `.so` encoder nhưng runtime vẫn cần tokenizer, `generate` và cache của thư viện.

## Kết luận

Chưa thể kết luận vì sandbox không có GPU: UserError: Constraints violated (encoder_sequence)! For more information, run with TORCH_LOGS="+dynamic".
  - Not all values of encoder_sequence = L['input_ids'].size()[1] in the specified range encoder_sequence <= 32768 satisfy the generated guard L['input_ids'].size()[1]*(8 + L['input_ids'].size()[1] + (-1)*(L['input_ids'].size()[1] % 8)) > 1.
Suggested fixes:
  _encoder_sequence = Dim('_encoder_sequence', min=1, max=4096)
  encoder_sequence = 8*_encoder_sequence - 1

The error above occurred when calling torch.export.export. If you would like to view some more information about this error, and get a list of all other errors that may occur in your export call, you can replace your `export()` call with `draft_export()`.
Khuyến nghị: chỉ thay torch.compile nếu lượt GPU cho ≥118/120 output giống hệt, median không quá 900 ms và gọi đầu giảm rõ rệt; nếu không, giữ cấu hình hiện tại.

## Điểm yếu

Mỗi câu đo một lần, một thứ tự và một máy; package phụ thuộc Torch/CUDA cùng ABI. Vì decoder chưa AOTI, phép đo này chỉ đánh giá phương án lai và không chứng minh full AOTI.
