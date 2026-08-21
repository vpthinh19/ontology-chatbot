# Đo ONNX Runtime

Đúng 120 ID từ `ket-qua-gpu.json`, model `_gop-bf16`, greedy, batch 1, tối đa 320 token, warm-up ngoài phép đo; input dài nhất 39 token (< cửa sổ 512), p95 nearest-rank. ONNX Runtime 1.29.0, float32, 8 CPU thread.

| runtime | đúng target | giống torch compile bf16 | median | p95 | nạp | gọi đầu |
|---|---:|---:|---:|---:|---:|---:|
| CT2 CPU int8 | 99/120 (82,5%) | — | 1.741 ms | — | — | — |
| CT2 GPU float32 | 99/120 (82,5%) | — | 1.219 ms | — | — | — |
| PyTorch compile bf16 GPU | 99/120 (82,5%) | 120/120 | 784 ms | 878 ms | 2.005 ms | 48.968 ms (compile+sinh) |
| ORT CPU float32 | 100/120 (83,3%) | 118/120 | 4.918 ms | 5.540 ms | 9.190 ms | 4.331 ms |
| ORT CUDA float32 | chưa đo | — | — | — | — | — |

CUDA chưa đo: sandbox không thấy GPU; lần thử provider CUDA không kích hoạt và lùi về CPU (ban đầu còn báo thiếu `libcublasLt.so.13`). Script đã preload wheel `nvidia-*`, sẵn sàng chạy lại bằng một lệnh trên máy GPU.

Hai lệch so với torch compile là `question-003592`, `question-004447`; ORT vẫn giống PyTorch CPU float32 119/120. Một lệch đổi đáp án sai thành đúng, nên đây là sai khác số học float32/backend, không phải dấu hiệu vòng KV-cache sai hàng loạt.

Ba tệp `.onnx`: encoder 1.073.477.881 B, decoder-init 1.744.763.602 B, decoder-cache 1.744.609.958 B; tổng 4,25 GiB. `onnxruntime-gpu` chiếm 0,274 GiB allocated; `tokenizers` 0,010 GiB.

Runtime **có** chạy không cần torch/transformers: subprocess đã sinh đúng tiền tố `SELECT`, và sau inference `sys.modules` cho `torch_loaded=false`, `transformers_loaded=false`; chỉ có `onnxruntime` và `tokenizers`.

So với image CT2 CPU-int8 thực (model/tokenizer 0,387 GiB + CT2 0,130 GiB), ONNX tối thiểu khoảng 4,565 GiB: **nặng thêm 4,05 GiB**, chủ yếu do hai decoder float32 lặp trọng số. So với image chứa đồng thời CT2-int8 + PyTorch bf16 + torch/transformers/nvidia-* hiện tại (~7,53 GiB), image ONNX giảm khoảng **2,97 GiB**, nếu CUDA libraries do base image/host cấp.

Kết luận: chưa nên bỏ CT2 sang bản ONNX này. Chất lượng giữ được (+0,8 điểm trên mẫu) nhưng CPU chậm 2,82× CT2, artifact lớn; CUDA còn thiếu số. Điểm cần cải thiện là gộp/chia sẻ trọng số decoder hoặc xuất bf16/quantize, rồi đo lại CUDA trên đúng máy đích.

Điểm yếu: mỗi câu chỉ đo một lần, một thứ tự/máy; p95 nhạy nhiễu; số CUDA và VRAM chưa có; phép tính container chưa cộng CUDA libraries nếu base image không cung cấp.
