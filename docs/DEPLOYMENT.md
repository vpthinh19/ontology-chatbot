# Triển khai

Checkpoint Transformers được chọn bằng validation, sau đó chuyển sang
CTranslate2 để runtime gọn và không phụ thuộc PyTorch.

## Chuyển đổi model sinh SPARQL

```bash
uv run --extra train convert_sparql_model \
  --model-dir artifacts/models/t5gemma2/model \
  --output-dir artifacts/deployment/t5gemma2 \
  --quantization int8
```

Sau chuyển đổi, phải chấm lại đúng test set:

```bash
uv run --extra inference evaluate_ct2_model \
  --model-dir artifacts/deployment/t5gemma2 \
  --output artifacts/deployment/t5gemma2/metrics.json
```

Chỉ dùng artifact nếu answer exact không giảm so với checkpoint Transformers.
Tokenizer, compatibility manifest và model binary phải nằm cùng thư mục để
runtime nạp đúng token ID đã dùng lúc train.

Transformers dùng `num_beams=1`, `do_sample=False`; CTranslate2 phải đặt rõ
`beam_size=1`. Đây là cùng một greedy decoding deterministic. Beam search chỉ
có thể được nghiên cứu như thí nghiệm phụ áp dụng đồng thời cho cả ba model,
không thuộc benchmark chính.

## Chuyển đổi domain gate

```bash
uv run --extra train convert_domain_gate \
  --source-dir artifacts/models/phobert-gate \
  --output-dir artifacts/deployment/phobert-gate \
  --quantization int8
```

Artifact gate chứa encoder CT2, tokenizer, `classifier.npz`, threshold và
checksum trong `manifest.json`. PyTorch chỉ cần ở bước conversion; webapp chạy
encoder bằng CTranslate2 và classification head bằng NumPy.

Đối chiếu artifact với prediction PyTorch đã lưu:

```bash
uv run --extra inference evaluate_domain_gate \
  --model-dir artifacts/deployment/phobert-gate \
  --dataset-dir resources/dataset/gate \
  --baseline-predictions artifacts/models/phobert-gate/test_predictions.jsonl \
  --output artifacts/deployment/phobert-gate/evaluation.json
```

Artifact chỉ được dùng khi ma trận nhầm lẫn không đổi, false acceptance rate
không quá 1,2% và recall trong miền đạt ít nhất 95%.

## Khởi động webapp

Khởi động API:

```bash
uv sync --extra inference
uv run --extra inference serve_sparql \
  --model-dir artifacts/deployment/t5gemma2 \
  --gate-model-dir artifacts/deployment/phobert-gate
```

API chuẩn hoá câu hỏi, kiểm tra phạm vi, sinh và xác minh `SELECT`, thực thi
trên ontology rồi trả văn bản trả lời. Câu ngoài phạm vi nhận thông báo ổn định
và không đi vào model sinh SPARQL. Ontology được mount như dữ liệu độc lập; cập nhật
literal không cần convert hay train lại model nếu schema/IRI không đổi.
