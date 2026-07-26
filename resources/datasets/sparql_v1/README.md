# SPARQL v1

Dataset dùng chung cho huấn luyện, chọn mô hình và đánh giá cuối:

- `train.jsonl`: dữ liệu mô hình được phép học;
- `val.jsonl`: dữ liệu dùng trong quá trình phát triển và chọn checkpoint;
- `test.jsonl`: dữ liệu chỉ dùng để báo cáo kết quả cuối;
- `manifest.json`: số lượng, phân bố và checksum của release.

Mỗi dòng có cùng một schema:

```json
{"id":"...","family_id":"...","register":"...","query_shape":"...","input":"...","target":"..."}
```

`family_id` gom các cách diễn đạt có cùng ý định và target để kiểm soát rò rỉ
giữa các tập. Với test v1, mỗi câu là một đơn vị đánh giá độc lập. `register`
mô tả phong cách câu hỏi; `query_shape` mô tả hình dạng SPARQL để phân tích lỗi.
Tên split nằm ở tên file nên không lặp lại trong từng record.

Đây là thay đổi cách đóng gói release v1, không phải đợt nâng cấp nội dung.
