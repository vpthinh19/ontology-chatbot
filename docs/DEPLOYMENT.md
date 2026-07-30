# Triển khai

Checkpoint triển khai là T5Gemma2 đã merge LoRA, chuyển sang CTranslate2 int8
và chấm end-to-end trên đúng 407 câu test khóa. Cả checkpoint Transformers và
artifact CT2 được công bố tại
<https://huggingface.co/vpthinh19/ntu-ontology-chatbot>.

## Artifact

Runtime đích chỉ nạp một checkpoint seq2seq đã chuyển sang CTranslate2 cùng
tokenizer và compatibility manifest. Không có artifact phân loại, classifier
head hoặc ngưỡng quyết định riêng.

Checkpoint PEFT được chọn bằng validation, merge vào base model thành checkpoint
Transformers độc lập, benchmark bằng `from_pretrained()`, rồi mới chuyển đổi.
Runtime không nạp adapter hoặc phụ thuộc PEFT. Artifact CTranslate2 phải được
chấm lại đúng test set để kiểm tra parity của output, Answer Exact và marker
exact.

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

CLI chỉ nhận một `--model-dir`, device, compute type, log level, host và port.
Không có model gate hoặc threshold thứ hai.

```bash
uv run --extra inference hf download vpthinh19/ntu-ontology-chatbot \
  --include 'ctranslate2/*' --local-dir artifacts/huggingface

uv run --extra inference serve_sparql \
  --model-dir artifacts/huggingface/ctranslate2 \
  --device cpu --compute-type int8 --host 127.0.0.1 --port 8000
```

Hoặc tự chuyển checkpoint Transformers vừa fine-tune:

```bash
uv run convert_sparql_model \
  --model-dir artifacts/model-benchmark/t5gemma2/model \
  --output-dir artifacts/deployment/t5gemma2-production \
  --quantization int8

uv run --extra inference serve_sparql \
  --model-dir artifacts/deployment/t5gemma2-production \
  --device cpu --compute-type int8 --host 127.0.0.1 --port 8000
```

Artifact CT2 lưu `model.bin`, tokenizer, config sinh và `manifest.json` chứa
phiên bản CT2, kiểu lượng tử hóa, nguồn checkpoint cùng SHA-256 từng file.

## Kiểm tra production

Trước khi dùng artifact:

1. kiểm tra checksum tokenizer/model/ontology;
2. chạy parity trên toàn test;
3. chạy ca thực tế trong `resources/cases/user_queries.txt`;
4. kiểm tra câu trong miền, ngoài miền, mơ hồ và hỗn hợp;
5. đo latency, memory và request đồng thời;
6. xác nhận log đủ để truy nguyên output model và SPARQL.

Các kiểm tra trên đã hoàn tất cho artifact int8 hiện tại. Kết quả web: 407/407
request trả HTTP 200; phản hồi hiển thị exact 378/407 (92,87%); CPU p50 300 ms,
p95 864 ms; probe tám request đồng thời thành công 8/8 ở 3,26 request/giây.
Nhóm noisy đạt 85,71% và là giới hạn chính cần lưu ý khi triển khai.
