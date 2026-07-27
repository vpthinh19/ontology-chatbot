# Stage G — nghiệm thu khả năng học của dataset v2

Stage G đã hoàn tất theo protocol khóa trước khi mở test của từng model. Ba checkpoint (3 model × seed 42) được chọn chỉ bằng validation; mỗi checkpoint chỉ đọc test một lần.

## Kết quả chính

| Model | Validation answer exact | Test answer exact | Test parse |
|---|---:|---:|---:|
| bartpho | 64.29% | 70.00% | 100.00% |
| vit5 | 68.57% | 63.57% | 99.29% |
| t5gemma2 | 74.29% | 77.86% | 100.00% |

`answer exact` nghĩa là kết quả dữ liệu khi chạy câu SPARQL sinh ra giống hệt kết quả của câu chuẩn; đây là chỉ số chất lượng chính. `parse` chỉ cho biết câu sinh ra có đúng cú pháp SPARQL, không đảm bảo model hiểu đúng câu hỏi.

## Dataset đã chứng minh được gì?

- BARTpho và ViT5 học thuộc tập kiểm tra nhỏ 16/16 sau 500 bước; T5Gemma2 được kiểm tra tokenizer toàn bộ target rồi train trực tiếp để tránh một lượt audit dư thừa.
- Cú pháp test đạt trên 99% ở cả ba model: lỗi chính không còn nằm ở dấu ngoặc hay tokenizer.
- T5Gemma2 đạt điểm validation và test cao nhất, đổi lại dùng nhiều VRAM nhất và sinh chậm nhất.

### Chi phí trên RTX 4050 6 GB

| Model | Thời gian train | VRAM train cực đại | Tốc độ test |
|---|---:|---:|---:|
| bartpho | 13.5 phút | 2.98 GiB | 6.53 câu/giây |
| vit5 | 13.3 phút | 2.35 GiB | 3.12 câu/giây |
| t5gemma2 | 19.0 phút | 4.84 GiB | 2.15 câu/giây |

## Giới hạn được Stage G phát hiện

| Model | 120 câu target đã thấy | 20 câu target mới |
|---|---:|---:|
| bartpho | 74.17% | 45.00% |
| vit5 | 68.33% | 35.00% |
| t5gemma2 | 81.67% | 55.00% |

- Có 16/140 câu sai ở cả ba model; 8 câu thuộc register `noisy`.
- Nhóm yếu nhất là `aggregate`, `multi_column` và câu nói thiếu dấu/viết tắt (`noisy`).
- Khoảng cách lớn ở target mới cho thấy coverage hiện tại chưa đủ mạnh cho ghép cấu trúc mới, không phải model không sinh được SPARQL.

## Kết luận

Dataset v2 **đủ tốt làm baseline nghiên cứu và phiên bản huấn luyện đầu tiên**, nhưng chưa đủ để coi bài toán tổng quát hóa đã giải quyết. Dataset v2 tiếp tục bị đóng băng vì test đã mở; mọi bổ sung dựa trên lỗi Stage G phải tạo thành v3 với test mới, tránh học ngược từ test.

Chi tiết máy đọc được, gồm điểm theo register/query shape, ba run và danh sách lỗi bền vững, nằm trong `stage_g_audit.json`.
