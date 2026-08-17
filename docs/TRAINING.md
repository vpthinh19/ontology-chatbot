# Huấn luyện mô hình

Tệp này trả lời cách dạy lại và chấm lại các mô hình trong dự án. Tệp dành cho kỹ sư có môi trường huấn luyện và cần các lệnh chạy, không cần đọc mã nguồn.

## Mô hình học gì

Mô hình nhận câu hỏi tiếng Việt và tạo một câu SPARQL hoặc “không có thông tin”. SPARQL là ngôn ngữ dùng để hỏi ontology. Ontology là tập dữ kiện và liên kết giúp máy tra cứu nội dung học vụ.

Dự án huấn luyện các mô hình seq2seq. Seq2seq là mô hình nhận một chuỗi chữ và tạo một chuỗi chữ khác; ở đây, chuỗi vào là câu hỏi và chuỗi ra là câu truy vấn.

## Chuẩn bị môi trường

```bash
uv sync --extra train
```

Lệnh này cài các thư viện cần cho huấn luyện và đánh giá.

## Chạy huấn luyện và chấm

```bash
bash train-server.sh
```

Lệnh này huấn luyện và chấm ba mô hình. Kết quả gồm các tệp đo và nhật ký để đối chiếu lại lượt chạy.

```bash
MODELS="t5gemma2" bash train-server.sh
```

Lệnh này chỉ chạy một mô hình khi cần kiểm tra riêng.

## Thời gian và phần cứng tham khảo

Một lượt huấn luyện một mô hình trong 3 epoch trên card đồ hoạ NVIDIA L4 24 GB mất khoảng 16 phút và dùng bộ nhớ card ở mức đỉnh 6,5 GB. Epoch là một lượt mô hình đi qua toàn bộ tập dạy.

Hệ thống có thể chạy trên card đồ hoạ 6 GB khi giảm cỡ lô. Cỡ lô là số câu hỏi được xử lý cùng lúc; giảm cỡ lô giảm bộ nhớ cần dùng nhưng có thể làm thời gian chạy dài hơn.

## Kiểm tra trước và sau khi huấn luyện

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests -q
```

Lệnh đầu kiểm tra bộ câu hỏi và 50 khuôn truy vấn có khớp dữ liệu hay không. Lệnh sau chạy các phép kiểm tự động của dự án.

Sau khi huấn luyện, dùng [Cách đo kết quả](EVALUATION.md) để chấm trên tập chỉnh và tập chấm. Không dùng tập chấm để chọn thiết lập huấn luyện.

## Vì sao tập chấm được giữ riêng

Tập chấm không tham gia chọn checkpoint. Checkpoint là bản lưu của mô hình tại
một thời điểm trong quá trình học; lượt chạy lưu nhiều bản và chọn một bản để
giữ lại. Việc chọn đó chỉ dùng tập chỉnh.

Nếu tập chấm tham gia chọn, con số cuối cùng không còn nói mô hình làm được gì
với câu hỏi chưa từng thấy - nó nói mô hình làm được gì với câu hỏi đã được dùng
để chọn ra chính nó. Tập chấm chỉ được mở sau khi mọi lựa chọn đã cố định.

## Giới hạn

- Kết quả huấn luyện chỉ cho biết khả năng đổi câu hỏi thành câu truy vấn và từ chối câu ngoài phạm vi.
- Kết quả không thay thế việc kiểm tra văn bản gốc trước khi trả lời một trường hợp có ảnh hưởng thực tế.
- Giọng gõ vội không dấu là dạng câu hỏi khó hơn trong dữ liệu.

## Tài liệu liên quan

- [Bộ câu hỏi](DATASET.md)
- [Cách đo kết quả](EVALUATION.md)
- [Đưa vào môi trường sử dụng](DEPLOYMENT.md)
