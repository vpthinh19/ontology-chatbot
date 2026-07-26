# Dataset audit v1

Audit read-only của `resources/datasets/sparql_v1`. Thư mục này không phải một
dataset release và không thay đổi record v1.

## Tái lập

Yêu cầu các artifact tokenizer và validation v1 đang có trên máy:

```bash
uv run --extra train audit_sparql_dataset \
  --output-dir reports/dataset_audit_v1 \
  --validation-metrics-root artifacts/sparql_official_v1 \
  --bartpho-tokenizer artifacts/sparql_deploy_v1/bartpho_seed21 \
  --vit5-tokenizer artifacts/tokenizers/vit5
```

Audit cố ý chỉ đọc `metrics.json` của validation. File
`benchmark_metrics.json` và kết quả test không được dùng để đặt ưu tiên sửa v2.

## Đầu ra

- `report.json`: số liệu đầy đủ, checksum và bằng chứng validation;
- `report.md`: bản tóm tắt dành cho người đọc;
- `family_review.jsonl`: worksheet; mọi quyết định của reviewer đang để trống.

Các cờ audit chỉ xếp thứ tự cần đọc. Chúng không tự động quyết định
`keep/fix/split/merge/drop` và không được dùng để sửa dữ liệu hàng loạt.
