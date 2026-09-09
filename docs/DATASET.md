# Bộ dữ liệu câu hỏi-đích truy xuất

Tài liệu này mô tả bộ dữ liệu dùng để huấn luyện và chấm bộ phân loại. Đây không
phải bộ câu trả lời học vụ và không phải tập hội thoại thu thập đại diện từ sinh
viên. Mỗi dòng ghép một câu hỏi tiếng Việt với một đích truy xuất có cấu trúc.

## 1. Hình dạng một dòng

```json
{
  "id": "question-000013",
  "query_id": "academic-actor-facts",
  "register": "noisy",
  "input": "co van hoc tap la ai",
  "target": [":AcademicAdvisor"]
}
```

| Trường | Ý nghĩa |
|---|---|
| `id` | mã duy nhất của câu hỏi |
| `input` | câu/cụm tiếng Việt đưa vào bộ phân loại |
| `query_id` | họ truy vấn trong catalogue |
| `target` | IRI điền vào slot của khuôn; rỗng cho từ chối |
| `register` | phong cách được gán trước: formal, neutral, colloquial, noisy |

Nhãn thô là `(query_id, target)`. Runtime đổi cặp này thành SPARQL bằng catalogue;
dataset không sao chép chuỗi truy vấn. Khi huấn luyện bộ phân loại, Khoản và Điểm
được gộp về Điều chứa chúng, làm 566 nhãn thô còn 344 nhãn phân loại.

## 2. Quy mô

| Split | Số dòng | Số đích thô | Mục đích |
|---|---:|---:|---|
| `train` | 5.523 | 566 | học tham số |
| `val` | 400 | 269 | theo dõi và điều chỉnh |
| `test` | 390 | 271 | chấm sau khi cố định lựa chọn |
| **Tổng** | **6.313** | **566** | 50 họ truy vấn |

`train` chứa toàn bộ đích thô. `val` và `test` chỉ chứa các đích đã biết, nên
benchmark đo cách hỏi mới về nội dung cũ, không đo thực thể mới.

| Miền | Số dòng |
|---|---:|
| Quy tắc học vụ | 1.742 |
| Thủ tục | 1.131 |
| Văn bản | 1.115 |
| Ngoài phạm vi | 829 |
| Biểu mẫu | 684 |
| Chứng chỉ | 476 |
| Học phí | 336 |

| Register | Số dòng |
|---|---:|
| colloquial | 1.800 |
| neutral | 1.640 |
| noisy | 1.490 |
| formal | 1.383 |

Độ dài trung vị 11 từ, trung bình 11,58, p95 21, phạm vi 1-36 từ.

## 3. Nguồn gốc câu hỏi

### 3.1 Câu trả lời được

Không gian đích lấy từ ontology và 49 họ trả lời được trong catalogue. Câu hỏi
được hình thành từ ba trục chính:

1. **Cách gọi thực thể**: nhãn chính, `skos:altLabel`, toạ độ điều khoản và phép
   rút gọn cơ học từ ontology.
2. **Khung ý định**: câu có chỗ trống được soạn tay theo từng họ, lưu tại
   [`frames.jsonl`](../resources/provenance/frames.jsonl).
3. **Phong cách**: tiền tố/hậu tố, chữ hoa, từ để hỏi tương đương và nhiễu bề mặt.

Ngoài câu tổ hợp, dự án có sổ
[`written-questions.jsonl`](../resources/provenance/written-questions.jsonl) cho
các câu soạn riêng. Sổ này không mang ID/split và không phải lineage đầy đủ
một-một cho mọi dòng hiện hành.

### 3.2 Câu từ chối

829 câu `no-information` được chia thành bảy lớp có checklist:

| Lớp | Số câu | Mục đích |
|---|---:|---|
| `hard-negative` | 163 | có tên thủ tục thật nhưng hỏi thuộc tính đồ thị không lưu |
| `near-domain-missing` | 151 | gần phạm vi nhưng thiếu dữ kiện cần trả |
| `unrelated` | 115 | chủ đề ngoài học vụ |
| `noisy-out-of-domain` | 109 | ngoài miền kèm lỗi gõ/bỏ dấu |
| `incomplete-request` | 108 | yêu cầu không nêu đủ chủ thể/nội dung |
| `greeting-social` | 94 | giao tiếp xã hội, không phải truy vấn dữ kiện |
| `adjacent-domain` | 89 | học vụ lân cận nhưng ontology chưa hỗ trợ |

[`rejection_provenance.json`](../resources/provenance/rejection_provenance.json)
ánh xạ từng ID từ chối về lớp, khuôn và neo. Nhóm `distraction` trong tệp khuôn
không phải lớp từ chối: đó là vế ngoài lề được ghép vào câu vẫn trả lời được.

## 4. Cách chia split

Mỗi họ trả lời được có các khung ý định riêng. Phần lớn khung dành cho `train`,
một khung dành cho `val` và một cho `test`. Các biến thể đồng nghĩa của cùng
khung ở cùng split. Cách chia này giảm việc test chỉ là hoán vị bề mặt của một
khung train.

Các kiểm tra hiện có xác nhận:

- không trùng nguyên văn giữa train và held-out;
- không trùng sau chuẩn hoá runtime và bỏ dấu;
- khung của ba split rời nhau theo quy tắc khai báo;
- mọi họ và slot IRI hữu hạn đều được train bao phủ;
- mọi đích trả lời được chạy SPARQL có kết quả;
- không có cùng một câu sau chuẩn hoá bị gán hai đích khác nhau;
- các register và lớp từ chối bắt buộc đều có mặt.

Việc cùng thực thể xuất hiện ở mọi split là có chủ đích. Do đó không gọi đây là
zero-shot hoặc đánh giá khả năng cập nhật quy định mới.

## 5. Dataset đo và không đo điều gì?

Dataset phù hợp để đo:

- exact-match label trong một miền truy vấn đóng;
- mức chịu biến thiên cách hỏi được tạo theo quy trình đã định;
- khả năng nhận nhãn từ chối trong bảy nhóm đã thiết kế;
- lỗi theo họ truy vấn, đích và register.

Dataset không đủ để đo:

- độ đúng hoặc độ đầy đủ pháp lý của ontology;
- chất lượng câu trả lời tự nhiên cuối cùng;
- phân bố câu hỏi thật của sinh viên;
- thực thể, thuộc tính hoặc văn bản chưa xuất hiện trong train;
- hội thoại nhiều lượt, đại từ phụ thuộc ngữ cảnh và thay đổi theo thời gian;
- hiệu năng trên mọi loại lỗi gõ ngoài ba cơ chế tổng hợp.

Register là nhãn thiết kế/tổng hợp, không phải nhãn do nhiều annotator độc lập
gán. 829 câu từ chối chiếm 13,1% do lựa chọn xây dựng dữ liệu; con số này không
ước lượng tỷ lệ câu ngoài phạm vi ở triển khai thật.

## 6. Kiểm tra

```bash
uv run validate_sparql_dataset
uv run pytest tests/research -q
```

Lệnh đầu kiểm ontology-inventory-catalogue-dataset-report và checksum. Lệnh sau
kiểm các bất biến nghiên cứu chi tiết. Hai lệnh không huấn luyện lại model.

## Tài liệu liên quan

- [README nghiên cứu](../README.md)
- [Ontology và nguồn](ONTOLOGY.md)
- [Câu hỏi phản biện](DEFENSE.md)
