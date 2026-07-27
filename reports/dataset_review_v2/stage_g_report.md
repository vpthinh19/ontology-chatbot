# Stage G — nghiệm thu khả năng học của dataset v2

Stage G đã hoàn tất theo protocol khóa trước khi mở test. Sáu checkpoint (2 model × 3 seed) được chọn chỉ bằng validation; mỗi checkpoint chỉ đọc test một lần.

## Kết quả chính

| Model | Validation answer exact | Test answer exact | Test parse | Test độ lệch chuẩn |
|---|---:|---:|---:|---:|
| bartpho | 66.43% | 65.95% | 99.52% | 3.93% |
| vit5 | 70.24% | 61.19% | 99.29% | 6.07% |

`answer exact` nghĩa là kết quả dữ liệu khi chạy câu SPARQL sinh ra giống hệt kết quả của câu chuẩn; đây là chỉ số chất lượng chính. `parse` chỉ cho biết câu sinh ra có đúng cú pháp SPARQL, không đảm bảo model hiểu đúng câu hỏi.

## Dataset đã chứng minh được gì?

- Cả hai model học thuộc tập kiểm tra nhỏ 16/16 sau 500 bước: pipeline, tokenizer và định dạng target không chặn việc học.
- Cú pháp test đạt trên 99% ở cả hai model: lỗi chính không còn nằm ở dấu ngoặc hay tokenizer.
- BARTpho có test trung bình cao và ổn định hơn ViT5, dù ViT5 cao hơn trên validation. Điều này cho thấy phải báo cáo nhiều seed và test độc lập.

## Giới hạn được Stage G phát hiện

| Model | 120 câu target đã thấy | 20 câu target mới |
|---|---:|---:|
| bartpho | 70.56% | 38.33% |
| vit5 | 66.67% | 28.33% |

- Có 23/140 câu sai trong cả sáu lượt chạy; 13 câu thuộc register `noisy`.
- Nhóm yếu nhất là `aggregate`, `multi_column` và câu nói thiếu dấu/viết tắt (`noisy`).
- Khoảng cách lớn ở target mới cho thấy coverage hiện tại chưa đủ mạnh cho ghép cấu trúc mới, không phải model không sinh được SPARQL.

## Kết luận

Dataset v2 **đủ tốt làm baseline nghiên cứu và phiên bản huấn luyện đầu tiên**, nhưng chưa đủ để coi bài toán tổng quát hóa đã giải quyết. Dataset v2 tiếp tục bị đóng băng vì test đã mở; mọi bổ sung dựa trên lỗi Stage G phải tạo thành v3 với test mới, tránh học ngược từ test.

Chi tiết máy đọc được, gồm điểm theo register/query shape, sáu run và danh sách lỗi bền vững, nằm trong `stage_g_audit.json`.
