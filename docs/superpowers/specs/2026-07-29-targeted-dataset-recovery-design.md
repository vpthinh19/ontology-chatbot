# Thiết kế phục hồi chất lượng dataset có mục tiêu

## Mục tiêu

Nâng chất lượng model chính bằng cách bù đúng các vùng yếu đã được T5Gemma2
chứng minh, không tái chia dataset và không mở rộng phạm vi ontology.

## Phạm vi cố định

- Giữ nguyên ba split train/validation/test.
- Sửa nhãn sai duy nhất đã xác minh: `question-002000`.
- Thêm 100–150 câu vào train; không chép nguyên câu validation/test.
- Không sửa ontology, catalogue, SPARQL schema, tokenizer, model architecture,
  hyperparameter hoặc preprocessing.
- Chỉ train lại T5Gemma2 một lần sau khi dataset và tokenizer đều hợp lệ.

## Nội dung bổ sung

Các câu mới ưu tiên ba nhóm:

1. family tổng hợp có 5–12 mẫu train và tỷ lệ lỗi cao;
2. cặp tương phản phân biệt property gần nghĩa trên cùng thực thể;
3. noisy tự nhiên giúp grounding đúng entity/IRI.

OOD chỉ bổ sung ít câu ambiguous/hard-negative nếu cần tạo ranh giới tương phản.
Không tăng greeting, unrelated, mixed hoặc noisy OOD vì các nhóm này đã đạt
100% trên test.

## Metric

`Answer Exact` tiếp tục đo output model. Báo cáo bổ sung
`system_answer_exact_rate`: câu trong miền phải trả đúng dữ liệu; câu ngoài miền
được xem là đúng ở cấp hệ thống nếu backend từ chối an toàn, kể cả query hợp lệ
nhưng trả rỗng. Prediction marker trên câu trong miền được phân loại là
`false_rejection`, không gọi là `parse_error`.

## Nghiệm thu

- Dataset, coverage, leakage và tokenizer audit đều qua.
- Test checksum chỉ thay đổi do sửa nhãn sai bắt buộc.
- T5Gemma2 được train đúng một run từ base model với giao thức đã khóa.
- Báo cáo đồng thời model Answer Exact, System Answer Exact, in-domain,
  out-of-domain, false acceptance và false rejection.
