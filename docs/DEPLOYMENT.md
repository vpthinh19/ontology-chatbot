# Triển khai

## Artifact

Runtime đích chỉ nạp một checkpoint seq2seq đã chuyển sang CTranslate2 cùng
tokenizer và compatibility manifest. Không có artifact phân loại, classifier
head hoặc ngưỡng quyết định riêng.

Checkpoint Transformers được chọn bằng validation, benchmark độc lập bằng
`from_pretrained()`, rồi mới chuyển đổi. Artifact CTranslate2 phải được chấm lại
đúng test set để kiểm tra parity của output, Answer Exact và marker exact.

Transformers dùng `num_beams=1`, `do_sample=False`; CTranslate2 dùng
`beam_size=1`. Beam search không thuộc benchmark hoặc production chính.

## Runtime

```text
input
→ normalize_model_input
→ CTranslate2 seq2seq
→ marker: Không có thông tin.
→ SELECT: validate → RDFLib → render
→ query lỗi/kết quả rỗng: Không có thông tin.
```

API trả HTTP 200 cho các phản hồi nghiệp vụ trên. Lỗi nạp model, ontology hoặc
lỗi lập trình vẫn là lỗi hệ thống.

Mỗi request được trace bằng một request ID. Log cấp INFO gồm input gốc, input
chuẩn hoá, output model nguyên văn, thời gian sinh, trạng thái xác minh, số dòng,
reply và tổng latency. Exception ghi stage cùng traceback.

## CLI

CLI triển khai phải chỉ nhận một `--model-dir`, device, compute type, log level,
host và port. Câu lệnh khởi động chỉ được công bố sau khi runtime hiện tại được
refactor và test end-to-end với artifact mới; lệnh yêu cầu model thứ hai không
thuộc contract này.

## Kiểm tra production

Trước khi dùng artifact:

1. kiểm tra checksum tokenizer/model/ontology;
2. chạy parity trên toàn test;
3. chạy ca thực tế trong `resources/cases/user_queries.txt`;
4. kiểm tra câu trong miền, ngoài miền, mơ hồ và hỗn hợp;
5. đo latency, memory và request đồng thời;
6. xác nhận log đủ để truy nguyên output model và SPARQL.
