# Cách đo kết quả

Tệp này trả lời kết quả được chấm theo tiêu chí nào và các con số báo cáo có nghĩa gì.

## Chỉ số

Benchmark là phép đo trên một tập dữ liệu giữ riêng, theo cùng quy tắc ở mọi lần chạy.

| Chỉ số | Câu hỏi được trả lời | Tập chỉnh | Tập chấm |
|---|---|---:|---:|
| Chọn đúng mục trong đồ thị | Mô hình có tìm đúng nơi chứa thông tin cần thiết không? | 80,2% | 76,4% |
| Dựng đúng dạng truy vấn | Câu truy vấn có khớp khuôn cho phép và đủ phần cần thiết không? | 85,5% | 81,8% |
| Từ chối đúng câu ngoài phạm vi | Mô hình có trả “không có thông tin” khi cần không? | 96,5% | 90,8% |

Không có điểm tổng hợp. Ba chỉ số được giữ riêng để cho thấy loại lỗi đang xảy ra.

## Cách đọc

- Chọn đúng mục không khẳng định mọi điều kiện và chi tiết của kết quả đều đúng.
- Dựng đúng dạng truy vấn chỉ xác nhận truy vấn thuộc khuôn hệ thống cho phép.
- Từ chối đúng giúp giảm nguy cơ trả lời cho câu hỏi ngoài dữ liệu.
- Các chỉ số không đo chất lượng của câu trả lời văn xuôi do lớp hội thoại bên ngoài viết.

## Chạy lại phép đo

```bash
uv run benchmark_model --seq2seq-model <thu_muc_mo_hinh> --split test --output artifacts/benchmark-test.json
uv run benchmark_sparql --details --output artifacts/evaluation/test.json
.venv/bin/python -m pytest tests/research/test_evaluation.py -q
```

Lệnh đầu chấm một mô hình chuỗi-chuỗi. Lệnh thứ hai chấm bộ dự đoán tham chiếu. Lệnh cuối kiểm tra quy tắc tính chỉ số.

## Tài liệu liên quan

- [Bộ câu hỏi](DATASET.md)
- [Thông tin về mô hình](MODEL_CARD.md)
