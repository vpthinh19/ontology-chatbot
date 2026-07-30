# Triển khai

Model triển khai là T5Gemma2 sau khi hợp nhất LoRA, chuyển sang CTranslate2 int8
và đánh giá end-to-end trên 407 câu test. Cả checkpoint Transformers và model
CTranslate2 được công bố tại
<https://huggingface.co/vpthinh19/ntu-ontology-chatbot>.

## Mô hình triển khai

Hệ thống chỉ nạp một checkpoint seq2seq đã chuyển sang CTranslate2 cùng
tokenizer và manifest tương thích. Không có model phân loại, classifier
head hoặc ngưỡng quyết định riêng.

Checkpoint PEFT được chọn bằng validation, merge vào base model thành checkpoint
Transformers độc lập, benchmark bằng `from_pretrained()`, rồi mới chuyển đổi.
Hệ thống không nạp adapter hoặc phụ thuộc PEFT. Model CTranslate2 được đánh giá
lại trên cùng tập test để kiểm tra tính tương đương của output, Answer Exact và marker
exact.

Runtime đọc trực tiếp `tokenizer.json` bằng thư viện `tokenizers`. Nó không cần
Transformers hoặc SentencePiece; hai dependency đó chỉ phục vụ huấn luyện và
benchmark các model nguồn.

Transformers dùng `num_beams=1`, `do_sample=False`; CTranslate2 dùng
`beam_size=1`. Beam search không thuộc benchmark hoặc production chính.

## Luồng xử lý

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

Thư mục CTranslate2 lưu `model.bin`, tokenizer, cấu hình sinh và `manifest.json` chứa
phiên bản CT2, kiểu lượng tử hóa, nguồn checkpoint cùng SHA-256 từng file.

## Kiểm tra triển khai

Trước khi sử dụng model:

1. kiểm tra checksum tokenizer/model/ontology;
2. chạy parity trên toàn test;
3. chạy ca thực tế trong `resources/cases/user_queries.txt`;
4. kiểm tra câu trong miền, ngoài miền, mơ hồ và hỗn hợp;
5. đo latency, memory và request đồng thời;
6. xác nhận log đủ để truy nguyên output model và SPARQL.

Kết quả kiểm tra model int8 trên web: 407/407 request trả HTTP 200; phản hồi
hiển thị chính xác 378/407 (92,87%); CPU p50 300 ms,
p95 864 ms; probe tám request đồng thời thành công 8/8 ở 3,26 request/giây.
Nhóm noisy đạt 85,71% và là giới hạn chính cần lưu ý khi triển khai.
