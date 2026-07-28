# Dataset

Dataset ánh xạ câu hỏi tiếng Việt tự nhiên sang một truy vấn SPARQL `SELECT`.
Mỗi dòng JSON Lines có năm trường:

```json
{
  "id": "question-0001",
  "query_id": "query-0001",
  "register": "formal",
  "input": "Tôi cần thực hiện thủ tục bảo lưu như thế nào?",
  "target": "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"
}
```

`query_id` định danh một truy vấn canonical và ánh xạ một-một tới `target`.
Nhiều câu hỏi được phép dùng chung `query_id`; đây là các cách diễn đạt khác
nhau của cùng chức năng mà chatbot công bố hỗ trợ.

## Phong cách câu hỏi

| Register | Cách diễn đạt |
|---|---|
| `formal` | Câu đầy đủ, gần văn phong hành chính |
| `neutral` | Cách hỏi phổ thông |
| `colloquial` | Ngôn ngữ nói thường ngày |
| `noisy` | Viết tắt, bỏ dấu hoặc câu rút gọn |

Trong từng split, số câu giữa register nhiều nhất và ít nhất chênh nhau không
quá một.

## Train, validation và test

| Tập | Câu hỏi | Query | Vai trò |
|---|---:|---:|---|
| Train | 1.403 | 215 | Cập nhật trọng số và dạy toàn bộ danh mục query |
| Validation | 430 | 215 | Chọn checkpoint bằng cách diễn đạt chưa thấy |
| Test | 430 | 215 | Đánh giá cuối bằng cách diễn đạt chưa thấy |

Mỗi query có đúng hai câu validation, hai câu test và toàn bộ câu còn lại ở
train; mỗi query có ít nhất bốn câu train và đủ cả bốn register. Hai câu của
mỗi tập held-out thuộc hai register khác nhau. Vì vậy
validation và test đo khả
năng hiểu cách nói mới trong miền chức năng đã dạy, không đo zero-shot trên
query hoặc ontology chưa biết. Test chỉ được dùng sau khi checkpoint được chọn.

![Phân bố dataset](../reports/figures/dataset-splits.svg)

## Hình dạng SPARQL

Dataset không lưu nhãn hình dạng truy vấn do một query có thể đồng thời nhiều
cột, đi qua graph, lọc, gom nhóm và sắp xếp. Báo cáo tự suy ra các đặc trưng
độc lập từ target: số cột, số triple pattern, object-property hop, aggregate,
`FILTER`, `GROUP BY`, `ORDER BY`, `LIMIT` và `VALUES` cho truy vấn nhiều thực
thể độc lập.

![Đặc trưng SPARQL](../reports/figures/query-features.svg)

## Khoảng trắng và padding

Target là một dòng và dùng khoảng trắng canonical để cả ba tokenizer bảo toàn
đúng SPARQL. Dynamic padding là token `<pad>` được thêm tạm khi tạo batch; nó
không nằm trong JSONL.

## Kiểm soát chất lượng

Trước khi huấn luyện, dataset phải qua các kiểm tra sau:

1. Mỗi bản ghi có đúng năm trường; ID là duy nhất.
2. Câu trùng hoặc gần trùng không rò rỉ giữa split.
3. `query_id` và target ánh xạ một-một.
4. Target parse được, chạy có kết quả và chỉ dùng contract SPARQL an toàn.
5. Toàn bộ 215 query xuất hiện trong cả train, validation và test.
6. Register cân bằng riêng trong từng split.
7. BARTpho, ViT5 và T5Gemma2 round-trip toàn bộ source/target không `<unk>` và
   không bị cắt.

Số liệu máy đọc, trạng thái sẵn sàng huấn luyện và checksum nằm trong
`reports/dataset.json` cùng `resources/dataset/main/manifest.json`.

## Dataset gate

`resources/dataset/gate/` dành cho bộ phân loại phạm vi đứng trước model sinh
SPARQL. Mỗi dòng JSON Lines có đúng hai trường:

```json
{"input":"đóng tiền học sao","label":"in_scope"}
```

`in_scope` nghĩa là ontology và contract SPARQL hiện tại có thể trả lời trọn
vẹn câu hỏi; `out_of_scope` bao gồm cả câu ngoài chủ đề và câu gần học vụ nhưng
đòi dữ liệu ontology không có. Dataset có 4.526 câu, cân bằng theo nhãn trong
từng split:

| Tập | Tổng | `in_scope` | `out_of_scope` |
|---|---:|---:|---:|
| Train | 2.806 | 1.403 | 1.403 |
| Validation | 860 | 430 | 430 |
| Test | 860 | 430 | 430 |

Toàn bộ câu hỏi của `dataset/main` xuất hiện ở phía `in_scope` của split tương
ứng. Validation dùng chọn ngưỡng; test chỉ dùng để báo cáo recall trong miền và
tỷ lệ nhận nhầm câu ngoài miền. Manifest cùng checksum nằm tại
`resources/dataset/gate/manifest.json`.
