# Dataset release

Thư mục này chứa ba split JSONL chuẩn của bộ phân loại và hai artifact mô tả
snapshot. Mô tả phương pháp đầy đủ nằm tại [`docs/DATASET.md`](../../docs/DATASET.md).

## Các tệp

| Tệp | Vai trò | Số dòng |
|---|---|---:|
| `train.jsonl` | học tham số | 5.523 |
| `val.jsonl` | theo dõi/điều chỉnh | 400 |
| `test.jsonl` | chấm sau khi cố định lựa chọn | 390 |
| **Tổng** | 50 họ truy vấn, 566 đích thô | **6.313** |

`coverage.json` khai các miền, register, trường hợp số và lớp từ chối bắt buộc.
`manifest.json` ghi số dòng, phân bố, slot và SHA-256 của dataset, ontology,
catalogue và coverage.

Tài nguyên liên quan nằm ngoài thư mục này:

| Tài nguyên | Vị trí |
|---|---|
| ontology | `resources/ontology/ontology.ttl` |
| catalogue 50 họ | `resources/ontology/catalogue.jsonl` |
| khung ý định | `resources/provenance/frames.jsonl` |
| câu soạn riêng | `resources/provenance/written-questions.jsonl` |
| khuôn và sổ câu từ chối | `resources/provenance/rejections.jsonl`, `rejection_provenance.json` |

## Hợp đồng dữ liệu

Mỗi dòng có `id`, `query_id`, `register`, `input` và `target`. Nhãn thô là cặp
`(query_id, target)`; chuỗi SPARQL được dựng từ catalogue. `no-information` có
`target=[]`.

Ba split không trùng câu sau chuẩn hoá/bỏ dấu. Mọi đích của val/test đã xuất hiện
trong train, nên benchmark đo cách hỏi mới về nội dung đã biết, không đo target
mới. Dataset chủ yếu được soạn/tổng hợp; không phải phân bố câu hỏi người dùng
thật.

## Kiểm tra

```bash
uv run validate_sparql_dataset
uv run pytest tests/research -q
```

Snapshot hiện được validator xác nhận bao phủ đủ catalogue và khớp các checksum.
Metric model không nằm trong manifest này.
