# Hoàn tất Stage E — chia train/validation/test theo family

Stage E chia nguyên vẹn 234 semantic family của `coverage_draft.jsonl`; không
sửa input, target, register hoặc metadata của bất kỳ record nào. Phép chia dùng
seed 42 và thuật toán deterministic được kiểm tra bằng cách sinh lại toàn bộ ba
file.

## Kết quả

| Split | Family | Record | Target | Tỷ lệ family |
|---|---:|---:|---:|---:|
| Train | 164 | 656 | 92 | 70,09% |
| Validation | 35 | 140 | 35 | 14,96% |
| Test | 35 | 140 | 35 | 14,96% |

Do mỗi family có đúng bốn register, từng split tự động cân bằng tuyệt đối:
train có 164 câu cho mỗi register, validation và test mỗi tập có 35 câu cho mỗi
register.

Phân bố query shape theo **family**:

| Query shape | Train | Validation | Test |
|---|---:|---:|---:|
| Direct | 79 | 17 | 15 |
| Graph hop | 55 | 12 | 12 |
| Multi-column | 20 | 4 | 5 |
| Aggregate | 8 | 1 | 2 |
| Aggregate + filter | 2 | 1 | 1 |

## Hai lớp đánh giá

Mỗi tập validation/test có 35 target khác nhau:

- 30 target đã có một family ngôn ngữ độc lập trong train, dùng để đo khả năng
  hiểu cách diễn đạt mới mà không rò paraphrase cùng family;
- 5 target chưa xuất hiện nguyên chuỗi trong train, mỗi query shape đúng một
  target, dùng làm compositional holdout nhỏ.

Compositional holdout không chứa schema lạ. Toàn bộ class, individual và
property cần sinh trong validation/test đã xuất hiện ở target train. Ví dụ,
train có cấu trúc thẻ liên hệ của Phòng Tài chính; validation và test yêu cầu
ghép cùng cấu trúc với Phòng Công tác Sinh viên và Phòng Đào tạo Đại học.

Năm family holdout của mỗi split được khóa rõ trong `stage_e_audit.json`, không
được chọn lại theo kết quả model. Validation và test không dùng chung target.

## Cổng review

- 936/936 record được bảo toàn, không đổi ID hoặc nội dung.
- Không family nào nằm ở hai split.
- Không exact duplicate sau normalizer hoặc near-duplicate xuyên split ở
  ngưỡng 0,84.
- Mọi split có đủ năm query shape và mọi target đều thực thi có kết quả trên
  ontology v12.
- Không ontology term nào của validation/test vắng mặt khỏi train.
- Không record nào của test v1 được đưa vào test v2.
- Checksum của source, ontology và ba split được ghi trong `manifest.json`.

`manifest.json` hiện có trạng thái `stage_e_candidate`. Stage F sẽ chạy toàn bộ
cổng release, audit lại tokenizer và chỉ đổi trạng thái sang frozen khi tất cả
đều đạt. Từ thời điểm này không dùng test v2 để sửa dataset, chọn checkpoint
hoặc điều chỉnh hyperparameter.
