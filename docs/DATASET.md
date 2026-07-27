# Dataset

Mỗi ví dụ là một cặp câu hỏi tiếng Việt và SPARQL. JSON Lines được dùng vì dễ
đọc tuần tự, dễ diff và tương thích trực tiếp với thư viện huấn luyện.

```json
{
  "id": "question-0001",
  "family_id": "family-0001",
  "register": "formal",
  "query_shape": "direct",
  "input": "...",
  "target": "SELECT ?answer WHERE { ... }"
}
```

`family_id` gom bốn câu cùng nghĩa. Nó ngăn một cách diễn đạt của cùng câu hỏi
lọt vào train trong khi cách khác lọt vào validation hoặc test.

## Bốn phong cách ngôn ngữ

| Register | Mục tiêu |
|---|---|
| `formal` | Câu đầy đủ, văn phong hành chính |
| `neutral` | Cách hỏi phổ thông |
| `colloquial` | Ngôn ngữ nói thường ngày |
| `noisy` | Viết tắt, bỏ dấu hoặc câu rút gọn |

Mỗi register hiện có đúng 334 câu. Các câu được viết và đọc lại theo ý nghĩa, không
sinh hàng loạt bằng một template thay từ.

## Chia tập

- Train: 1.040 câu / 260 họ, dùng cập nhật trọng số.
- Validation: 140 câu / 35 họ, dùng chọn checkpoint. Họ câu chưa thấy nhưng
  target đã có trong train, nên đo khả năng hiểu paraphrase.
- Test: 156 câu / 39 họ. Target chưa xuất hiện trong train hoặc validation,
  nhưng từng IRI/property cấu thành đã có trong train, nên đo khả năng ghép
  truy vấn mới.

Test có truy vấn trực tiếp, đi qua graph, nhiều cột, đếm và lọc/sắp xếp. Không
có rò rỉ family, câu trùng hoặc câu gần trùng giữa các tập.

![Hình dạng truy vấn](../reports/figures/query-shapes.svg)

## Các cổng chất lượng

Một dataset hợp lệ phải thỏa tất cả điều kiện sau:

1. Đúng sáu field và tập giá trị register/query shape.
2. ID, family và câu đã chuẩn hóa không rò rỉ giữa split.
3. Mỗi family chỉ có một target.
4. Target là một dòng, parse được, không có ký tự tokenizer không bảo toàn.
5. Target chạy trên ontology và trả ít nhất một dòng.
6. Target test chưa thấy nhưng không dùng schema term chưa học.
7. BARTpho, ViT5 và T5Gemma2 encode/decode toàn bộ target không có `<unk>`.

Manifest và thống kê đầy đủ nằm trong `resources/dataset/manifest.json` và
`reports/dataset.json`.

## Khoảng trắng và padding

Target dùng một khoảng trắng canonical quanh các thành phần SPARQL để cả ba
tokenizer encode/decode chính xác. Đây là dữ liệu thật trong JSONL. Dynamic
padding là token `<pad>` chỉ được collator thêm tạm theo batch và không được ghi
vào dataset.

## Audit trước benchmark

Dataset hiện đã tăng từ 1.176 lên 1.336 câu bằng 40 family train mới, tập trung
vào nhiều cột, nhiều nhánh, lọc, sắp xếp và tổng hợp. Toàn bộ target parse được,
chạy có kết quả; các register cân bằng; class/property của ontology đều được
phủ; không có schema term hoàn toàn mới trong test.

Việc bổ sung này chưa đủ để chạy benchmark chính thức. Các vấn đề phải xử lý:

1. Validation chưa có `aggregate_filter`, `FILTER`, `GROUP BY`, `ORDER BY` hoặc
   `LIMIT`, nên chưa đo được năng lực mới để chọn checkpoint.
2. Cả 40 target mới chỉ có một family. Hiện 97/163 target train, 44/52 target
   nhiều cột và 12/12 target `aggregate_filter` chỉ có một family.
3. `BankCounterPayment`, `OnlinePayment`, `PaymentMethod` và
   `PlanningAndFinanceOffice` chỉ có một family train nhưng xuất hiện trong
   test.
4. Test có 19/39 family nhiều cột nhưng chỉ có 4 family direct, 4 aggregate và
   4 aggregate/filter; điểm tổng bị chi phối bởi một query shape.
5. Dataset chưa phủ câu hỏi lấy cùng thuộc tính từ hai hoặc nhiều thực thể độc
   lập; chưa có `UNION` hay `VALUES` để biểu diễn trường hợp này.
6. `family-0311`, `family-0325`, `family-0327` có câu hỏi rộng hơn dữ liệu query
   thực trả; `family-0334` bị gán sai query shape. Các truy vấn top/bottom cần
   thứ tự phụ để kết quả xác định khi đồng hạng.
7. Validator chưa bắt đủ bốn register/family, near-duplicate theo ngưỡng,
   query-shape sai cấu trúc, mức hỗ trợ schema term và độ phủ validation.
8. 39 target test hiện tạo 35 bảng kết quả khác nhau. Đây không phải lỗi ở góc
   độ câu trả lời hiển thị, nhưng answer exact phải luôn đi cùng query string
   exact và phân tích lỗi để tránh hiểu nhầm là model đã sinh đúng quan hệ.

Chỉ được train benchmark sau khi sửa nội dung, bổ sung coverage có mục tiêu,
đọc lại thủ công các family mới và xuất báo cáo coverage có thể tái lập. Chất
lượng và độ phủ quan trọng hơn tăng số mẫu bằng template.
