# Huấn luyện mô hình

Tệp này trả lời cách chạy lại quy trình huấn luyện và chấm bốn mô hình.

## Phạm vi

Bốn mô hình là các mô hình chuỗi-chuỗi do bốn tổ chức phát triển. Chúng nhận câu hỏi tiếng Việt và tạo SPARQL hoặc “không có thông tin”. SPARQL là ngôn ngữ hỏi ontology.

## Chuẩn bị môi trường

```bash
uv sync --extra train
```

Lệnh này cài các thư viện cần cho quy trình huấn luyện và đánh giá.

## Chạy quy trình

```bash
bash train-server.sh
```

Lệnh này chạy quy trình cho bốn mô hình và lưu kết quả để đối chiếu.

## Kiểm tra trước và sau khi chạy

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests -q
```

Lệnh đầu kiểm tra bộ câu hỏi và khuôn truy vấn có khớp dữ liệu. Lệnh sau chạy các phép kiểm tự động của dự án.

Sau khi chạy, dùng [Cách đo kết quả](EVALUATION.md) để chấm trên tập chỉnh và tập chấm.

## Tập chấm được giữ riêng

Tập chấm không tham gia chọn checkpoint. Việc chọn đó chỉ dùng tập chỉnh. Tập chấm chỉ được mở sau khi các lựa chọn đã cố định.

## Tài liệu liên quan

- [Bộ câu hỏi](DATASET.md)
- [Cách đo kết quả](EVALUATION.md)
