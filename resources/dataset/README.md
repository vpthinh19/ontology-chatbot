# Dataset

## Các tệp và số dòng

| Tệp | Vai trò | Số dòng |
|---|---|---:|
| `train.jsonl` | ví dụ huấn luyện | 4.271 |
| `val.jsonl` | kiểm định | 406 |
| `test.jsonl` | kiểm tra cuối | 387 |
| **Tổng** |  | **5.064** |

Số dòng được đếm trực tiếp từ ba JSONL và khớp với `reports/dataset.json`.

Các tệp hỗ trợ:

| Tệp | Vai trò |
|---|---|
| `catalogue.jsonl` | danh mục truy vấn v3 |
| `catalogue-manual.jsonl` | họ viết tay được trộn vào catalogue |
| `frames.jsonl` | khung diễn đạt theo họ |
| `coverage.json` | hợp đồng độ phủ |
| `manifest.json` | checksum và hợp đồng split |
| `rejections.jsonl` | khung câu ngoài phạm vi |

## Catalogue v3

Catalogue hiện có **50 họ**. Hình dạng chính là các họ `*-facts`: neo một node,
lấy literal trên node và node con trực tiếp, rồi trả
`?thuoctinh ?giatri ?nguon ?duongdan`. Bảng có họ riêng trả toàn
`verbatimTableText` của node bảng.

Catalogue không còn coi từng thuộc tính nhỏ hay từng cell bảng là một mục tiêu
truy xuất độc lập. Mỗi bảng là một node nguyên văn.

## Trạng thái

Ba split, frame và catalogue đã đồng bộ. Release phủ đủ 50 họ, 781/781 tên gọi
và tám lớp câu từ chối; val/test không rò câu đã chuẩn hoá từ train. Manifest và
report được sinh cùng chuỗi với các JSONL, rồi được kiểm checksum read-only.

## Kiểm tra

```bash
uv run validate_sparql_dataset
.venv/bin/python -m pytest tests/research -q
```

Tập test không tham gia chọn checkpoint hoặc prompt. Không công bố metric model
trước khi các lệnh kiểm tra dữ liệu xanh.
