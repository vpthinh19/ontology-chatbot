# Đo PyTorch so với CTranslate2

Đo 120 câu, greedy, batch 1, mỗi câu đúng một lần gọi, warm-up ngoài phép đo; p95 nearest-rank. PyTorch 2.13.0+cu130, CPU x86_64; CUDA: True.

| cấu hình | trạng thái | đúng target | giống CT2 cpu-int8 | giống CT2 gpu-f32 | median ms | p95 ms | nạp ms | compile đầu ms | VRAM MiB |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cpu-float32 | ok | 99/120 (82.5%) | 116/120 | 120/120 | 7,872 | 8,820 | 2,448 | — | — |
| cpu-bfloat16 | chưa đo được: chưa có kết quả trong môi trường khả dụng | — | — | — | — | — | — | — | — |
| cuda-float32 | chưa đo được: chưa có kết quả trong môi trường khả dụng | — | — | — | — | — | — | — | — |
| cuda-bfloat16 | ok | 99/120 (82.5%) | 115/120 | 119/120 | 3,166 | 8,016 | 3,172 | — | 1,526 |
| cuda-bfloat16-compile | ok | 99/120 (82.5%) | 115/120 | 119/120 | 784 | 878 | 2,006 | 48,968 | 1,546 |
| cuda-float32-compile | chưa đo được: chưa có kết quả trong môi trường khả dụng | — | — | — | — | — | — | — | — |

## So sánh trực tiếp

Mốc CT2: cpu-int8 82,5% / 1.741 ms; gpu-float32 82,5% / 1.219 ms; gpu-bfloat16 80,8% / 692 ms.
PyTorch CUDA bfloat16 đạt 82.5% / 3,166 ms: hơn CT2 bf16 1,7 điểm %, nhưng chậm 4.58×; VRAM đỉnh 1,526 MiB.
Sandbox chính không thấy GPU; chưa đo được cuda-float32, cuda-float32-compile.

## Dung lượng site-packages (allocated GiB)

| torch | transformers | ctranslate2 | nvidia-* (tổng) | PyTorch stack trừ CT2 |
|---:|---:|---:|---:|---:|
| 1.05 | 0.05 | 0.13 | 4.42 | +5.39 GiB |

Bỏ CT2 chỉ tiết kiệm 0.13 GiB; nếu ảnh CT2 hiện không cần torch/transformers/nvidia-*, chuyển native làm container nặng thêm khoảng 5.39 GiB. Nếu các gói đó đã có vì tác vụ khác, phần chênh biên chỉ là −0.13 GiB.

## Khuyến nghị

Giữ CT2: PyTorch CUDA bf16 đạt chất lượng benchmark nhưng chậm hơn rõ rệt, CPU cũng không thắng (nếu có số), trong khi stack native làm ảnh nặng thêm. Compile chưa có số để đảo ngược kết luận.

## Điểm yếu phép đo

Mỗi câu chỉ đo một lần nên percentile nhạy với nhiễu; chỉ một thứ tự câu và một máy. Lượt GPU bf16 bên ngoài chồng thời gian với một lượt CPU nên có thể tranh chấp tài nguyên. Load float32 gồm gộp LoRA trong RAM (có thể giảm nếu đóng gói sẵn). Compile đầu là cả biên dịch+lần sinh đầu. Dung lượng là môi trường hiện tại, không phải image tối giản; ba cấu hình CUDA còn thiếu.
