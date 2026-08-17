# Cách đo kết quả

Tệp này trả lời kết quả của mô hình được chấm theo tiêu chí nào và các con số trong README có nghĩa gì. Tệp dành cho giảng viên, người đánh giá và kỹ sư chạy lại phép đo.

## Ba chỉ số chính

Benchmark là phép đo được chạy trên một tập dữ liệu đã giữ riêng để so sánh kết quả theo cùng quy tắc. Dự án báo ba chỉ số riêng vì mỗi chỉ số trả lời một câu hỏi khác nhau.

| Chỉ số | Câu hỏi được trả lời | Tập chỉnh | Tập chấm |
|---|---|---:|---:|
| Chọn đúng mục trong đồ thị | Mô hình có tìm đúng nơi chứa thông tin cần thiết không? | 80,2% | 76,4% |
| Dựng đúng dạng truy vấn | Câu truy vấn có khớp khuôn được phép và đủ phần cần thiết không? | 85,5% | 81,8% |
| Từ chối đúng câu ngoài phạm vi | Mô hình có trả “không có thông tin” khi cần không? | 96,5% | 90,8% |

Đồ thị tri thức là tập dữ kiện và liên kết giúp tra cứu quy định theo cấu trúc. Một node là một mục trong đồ thị, chẳng hạn một thủ tục hoặc bảng. SPARQL là ngôn ngữ dùng để hỏi đồ thị; mô hình tạo SPARQL ở bên trong hệ thống.

## Cách đọc các chỉ số

- Chọn đúng mục trong đồ thị chưa khẳng định mọi điều kiện và mọi chi tiết của kết quả đều đúng.
- Dựng đúng dạng truy vấn xác nhận câu truy vấn thuộc một trong 50 khuôn hệ thống cho phép chạy.
- Từ chối đúng giúp giảm nguy cơ trả lời cho một câu hỏi không thuộc dữ liệu dự án.
- Không có điểm tổng hợp. Ba chỉ số được giữ riêng để người đọc thấy rõ loại lỗi nào đang xảy ra.

## Tập dùng để đo

| Tập | Số dòng | Vai trò trong phép đo |
|---|---:|---|
| Tập chỉnh | 400 | Dùng khi chọn thiết lập trước khi chấm cuối. |
| Tập chấm | 390 | Dùng để báo kết quả cuối sau khi lựa chọn đã cố định. |

Kết quả trên hai tập không thay thế cho việc đánh giá câu trả lời bằng văn xuôi của một lớp hội thoại bên ngoài. Các chỉ số ở đây chỉ đo bước đổi câu hỏi thành truy vấn và bước tra cứu có kiểm soát.

## Chạy lại phép đo

Mô hình được chấm ở đây là mô hình xử lý chuỗi-thành-chuỗi, còn gọi là seq2seq: mô hình nhận một chuỗi chữ và tạo một chuỗi chữ khác.

```bash
uv run benchmark_model --seq2seq-model <thu_muc_mo_hinh> --split test --output artifacts/benchmark-test.json
```

Thay `<thu_muc_mo_hinh>` bằng thư mục mô hình cần chấm.

```bash
uv run benchmark_sparql --benchmark resources/dataset/val.jsonl --predictions artifacts/val-predictions.jsonl --details --output artifacts/evaluation/val.json
.venv/bin/python -m pytest tests/research/test_evaluation.py -q
```

Lệnh đầu chấm một tệp dự đoán có sẵn. Lệnh sau kiểm tra riêng các quy tắc tính chỉ số.

## Giới hạn của phép đo

- Một câu truy vấn có thể chọn đúng node nhưng vẫn thiếu điều kiện hoặc lấy sai phần dữ liệu.
- Kết quả không đo việc người dùng hiểu câu trả lời hay có thể hoàn tất thủ tục.
- Kết quả không đo độ chính xác của nội dung do một mô hình ngôn ngữ lớn diễn đạt thêm bên ngoài công cụ.

## Tài liệu liên quan

- [Bộ câu hỏi](DATASET.md)
- [Huấn luyện](TRAINING.md)
- [Thông tin về mô hình](MODEL_CARD.md)
