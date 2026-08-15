# Báo cáo dẫn xuất

Thư mục này chỉ được dùng làm nguồn cho thống kê artifact có thể tái tạo. Không
có báo cáo model hợp lệ trong repository và tài liệu công khai không công bố kết
quả model cũ.

## Artifact được dùng

- `dataset.json`: số dòng ba split, phân bố miền/register, đặc trưng query và
  checksum tại thời điểm report được sinh;
- `procedure-dataset.json`: snapshot dẫn xuất về các target thủ tục;
- `provenance.json`: fingerprint input và trạng thái vô hiệu của metric model,
  deployment;
- `figures/dataset-splits.svg`, `figures/registers.svg` và
  `figures/query-features.svg`: hình dẫn xuất từ thống kê dataset.

Ba split JSONL hiện có 4.271, 402 và 383 dòng, tổng **5.064 câu**.
`dataset.json` ghi cùng các số này và `training_readiness.ready = true` sau khi
đối chiếu coverage, tên gọi, target và catalogue hiện hành.

`provenance.json` giữ `model_metrics.status = stale` và
`deployment_metrics.status = stale` để tránh diễn giải nhầm artifact cũ. Nó
không phải nguồn metric và không biến model cũ thành baseline. Fingerprint này
được nhận từ **baseline v0.4.1**; `reports/provenance.json` là nơi phân biệt
input baseline với input hiện hành.

## Tái tạo

Kiểm tra read-only:

```bash
uv run validate_sparql_dataset
```

Chỉ khi input đã đồng bộ và việc ghi artifact được cho phép mới chạy:

```bash
uv run generate_reports
```

Chuỗi sinh report cũng ghi `procedure-dataset.json`, manifest và các hình từ
cùng một snapshot để các artifact không trôi lệch nhau.
