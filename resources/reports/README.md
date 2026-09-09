# Báo cáo dẫn xuất

Thư mục này chứa báo cáo thống kê dẫn xuất từ snapshot ontology, catalogue và
dataset. Nó không phải nguồn dữ liệu gốc và không phải nơi phát hành model.

## Nội dung

- `dataset.json`: 6.313 dòng (5.523 train, 400 val, 390 test), phân bố miền và
  register, đặc trưng truy vấn, thống kê ontology, coverage và checksum;
- `procedure-dataset.json`: snapshot dẫn xuất về các đích thủ tục;
- `audit-bon-dieu-kien.json`: kết quả kiểm bốn điều kiện dữ liệu;
- `provenance.json`: fingerprint dùng để đối chiếu các tệp đầu vào cục bộ;
- `figures/`: hình SVG sinh từ `dataset.json`.

`dataset.json` ghi `training_readiness.ready=true`, coverage 50 họ đầy đủ và
790/790 cách gọi được phủ. Các số này mô tả tính đầy đủ theo hợp đồng khai báo,
không phải hiệu năng model. Kết quả benchmark mới nhất được báo trong README;
mô hình phục vụ được phát hành riêng trên Hugging Face Hub và Docker Hub.

## Tái tạo

Kiểm chỉ đọc:

```bash
uv run validate_sparql_dataset
```

Chỉ chạy lệnh ghi sau khi chủ động muốn cập nhật toàn bộ artifact dẫn xuất:

```bash
uv run generate_reports
```

Chuỗi sinh report cập nhật `dataset.json`, `procedure-dataset.json`, manifest,
provenance và các hình từ cùng snapshot. Nó không huấn luyện hoặc chấm model.
