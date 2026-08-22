# artifacts/ — cái gì nằm ở đâu

Thư mục này giữ kết quả chạy trên máy: trọng số model, dự đoán từng câu, số đo tốc
độ. Git chỉ theo dõi **bộ dựng hình** và chính tệp này; phần còn lại dựng lại được
nên không đưa vào kho mã.

| Thư mục | Nội dung | Trong git | Dựng lại bằng |
|---|---|---|---|
| `figures/` | Nguồn của mọi hình trong tài liệu: năm sơ đồ Graphviz và bộ dựng biểu đồ | có | — |
| `entity-linking/` | Model đã huấn luyện, dự đoán từng câu, chỉ số so sánh | không | `train_classifier` rồi `benchmark_classifier` |
| `notes/` | Biên bản kiểm định và rà soát nội bộ | không | — |

## Vì sao `figures/` được theo dõi còn ảnh thì không nằm ở đây

`figures/` là **mã nguồn**: năm tệp `.dot` và các script dựng biểu đồ. Ảnh chúng
sinh ra nằm ở `docs/images/` vì `README.md` nhúng trực tiếp — một bản sao mới của
kho mã phải hiển thị được tài liệu mà không cần chạy gì.

Dựng lại sơ đồ:

```
dot -Tpng -Gdpi=150 artifacts/figures/architecture.dot -o docs/images/kien-truc.png
```

Dựng lại biểu đồ kết quả:

```
benchmark_classifier
```

## `entity-linking/`

| Tệp | Nội dung |
|---|---|
| `model-<tên>/` | Bộ điều hợp, lớp phân loại và bảng nhãn của từng model |
| `preds-<tên>.npz` | Dự đoán và biểu diễn từng câu trên `val` và `test` |
| `cls-<tên>.json` | Lịch sử loss, thời gian huấn luyện, điểm theo nhóm |
| `benchmark-metrics.json` | Chỉ số của cả năm model, nguồn cho bảng và hình |
| `index.jsonl` | Kho thẻ xuất từ ontology, để đối chiếu ngoài lúc chạy |

Model nặng nhất khoảng 20 MB vì bảng nhúng của bộ mã hoá đa ngữ lớn. Một lượt huấn
luyện lại mất khoảng ba phút cho mỗi model.
