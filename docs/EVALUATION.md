# Cách đo kết quả

Tệp này trả lời kết quả được chấm theo tiêu chí nào và các con số báo cáo có nghĩa gì.

## Chỉ số

Benchmark là phép đo trên một tập dữ liệu giữ riêng, theo cùng quy tắc ở mọi lần chạy.

| Chỉ số | Câu hỏi được trả lời | Mẫu số |
|---|---|---|
| Chọn đúng mục trong đồ thị | Mô hình có tìm đúng nơi chứa thông tin cần thiết không? | chỉ câu trong phạm vi (344 ở tập chỉnh, 335 ở tập chấm) |
| Dựng đúng dạng truy vấn | Câu truy vấn có khớp khuôn cho phép và điền đúng mọi phần không phải tên mục không? | chỉ câu trong phạm vi (344 / 335) |
| Bắt đúng câu ngoài phạm vi | Mô hình có trả “không có thông tin” cho câu ngoài phạm vi không? | chỉ câu ngoài phạm vi (56 / 55) |
| Không từ chối oan | Mô hình có tránh từ chối nhầm câu trả lời được không? | chỉ câu trong phạm vi (344 / 335) |

Không có điểm tổng hợp. Bốn chỉ số được giữ riêng để cho thấy loại lỗi đang xảy ra.

**Con số của từng mô hình nằm trong [README](../README.md)**, mục kết quả thực nghiệm.
Tài liệu này chỉ định nghĩa chỉ số, không chép lại số liệu — chép hai nơi là tạo thêm
một chỗ để số liệu trôi lệch.

## Cách đọc

- Chọn đúng mục không khẳng định mọi điều kiện và chi tiết của kết quả đều đúng.
- Dựng đúng dạng truy vấn đòi hỏi truy vấn thuộc đúng họ khuôn **và** điền đúng mọi phần
  không phải tên mục. Tên mục được chấm riêng, nên một truy vấn có thể đúng dạng mà vẫn
  trỏ sai mục.
- Hai chỉ số về từ chối là **hai mặt của cùng một quyết định** và phải đọc cùng nhau.
  Mô hình dè dặt sẽ bắt được nhiều câu ngoài phạm vi hơn nhưng cũng chặn nhầm nhiều câu
  hợp lệ hơn. Gộp chúng thành một tỷ lệ chung sẽ bị nhóm câu đông hơn lấn át.
- Các chỉ số trên đo **truy vấn do mô hình sinh ra**, không đo chất lượng câu trả lời văn
  xuôi do lớp hội thoại bên ngoài viết. Câu trả lời được chấm riêng, xem README.

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
