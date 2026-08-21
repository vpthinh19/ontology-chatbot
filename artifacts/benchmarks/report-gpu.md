# Đo CTranslate2 CPU/GPU ngày 2026-08-19

## Phạm vi và giao thức

- Đã chuyển đúng một lần model gộp LoRA sang `artifacts/ct2/t5gemma2-f32/` với `float32`; tổng artifact 1.536.165.466 byte. Hash artifact `artifacts/ct2/t5gemma2` trước/sau giống hệt nhau.
- Đo 120/335 câu có đích SPARQL vì CPU cần khoảng 10 phút cho 335 câu: lấy tất định seed 42, đúng 30 câu cho mỗi register formal/neutral/colloquial/noisy.
- Mọi cấu hình: CTranslate2 4.8.1, seed 42, greedy `beam_size=1`, `max_decoding_length=320`, batch 1; warm-up 1 câu ngoài phép đo, rồi mỗi câu đúng một lần gọi. p95 dùng nearest-rank.
- “Khác kết quả” so tập hàng không phụ thuộc thứ tự/tên biến; lỗi cú pháp/thực thi là outcome riêng. Đơn vị độ trễ là ms; VRAM là byte của tiến trình.

## Kết quả

| # | Thiết bị | compute_type | Trạng thái | Sai cú pháp | Khác nguyên văn với CPU | Khác kết quả với CPU | Median (ms) | p95 (ms) | VRAM đỉnh |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | cpu | int8 | chạy đủ 120 | 2 | 0 | 0 | 1770.926021 | 2025.117562 | không áp dụng |
| 2 | cuda | bfloat16 | không nạp được | — | — | — | — | — | không đo được |
| 3 | cuda | int8_bfloat16 | không nạp được | — | — | — | — | — | không đo được |
| 4 | cuda | float16 | không nạp được | — | — | — | — | — | — | không đo được |
| 5 | cuda | int8_float16 | không nạp được | — | — | — | — | — | — | không đo được |

Cả bốn lượt CUDA cùng lỗi nguyên văn: `RuntimeError: CUDA failed with error no CUDA-capable device is detected`. Máy có RTX 4050 và module NVIDIA 610.57.04 đang nạp, nhưng môi trường thi công không có `/dev/nvidia*`; `nvidia-smi` không liên lạc được driver và PyTorch thấy 0 GPU.

Hai lỗi CPU là `question-003339` (noisy) và `question-003689` (colloquial): model sinh đúng marker `không có thông tin` cho câu trong miền, nên không parse thành SPARQL; không phải tràn số.

## Kết luận và khuyến nghị

- Trong môi trường phục vụ hiện đo được, GPU **không dùng được** vì thiết bị CUDA không được cấp cho tiến trình. Không compute type GPU nào được chứng minh an toàn hay không an toàn trên RTX 4050/L4 từ lượt này.
- Hệ số nhanh GPU/CPU và phép thử độ trễ bổ sung ở Việc 3: **không đo được**; không có kiểu GPU an toàn để chạy. Mốc CPU thật là median 1.770926021 s/câu và p95 2.025117562 s/câu.
- Giả thuyết “float16 tràn còn bfloat16 không tràn” **không được dữ liệu phép đo này ủng hộ** (cũng chưa thể bác bỏ), vì mọi kiểu CUDA dừng trước suy luận; số cũ 11/60 không cùng lượt đối chứng nên không dùng để suy nguyên nhân.
- Khuyến nghị hiện tại: tiếp tục phục vụ CPU `int8`; chưa chuyển L4. Sau khi cấp `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`, chạy lại chính `do-gpu.py`; chỉ chọn `int8_bfloat16` hoặc `bfloat16` nếu sai cú pháp = 2/120, khác kết quả = 0 và độ trễ tốt hơn CPU.
- Điểm yếu: chỉ 120/335 câu, một lần sinh/câu, một máy; GPU/VRAM chưa đo được; baseline có 2 marker sai miền nên “an toàn” ở đây chỉ có nghĩa không kém mốc, không phải tuyệt đối 0 lỗi.

Bằng chứng thô: `ket-qua-gpu.json`; chương trình tái lập: `do-gpu.py`.
