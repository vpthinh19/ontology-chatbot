# Triển khai

Checkpoint Transformers được chọn bằng validation, sau đó chuyển sang
CTranslate2 để runtime gọn và không phụ thuộc PyTorch.

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

Khởi động API:

```bash
uv sync --extra inference
uv run --extra inference serve_sparql \
  --model-dir artifacts/deployment/t5gemma2
```

API nhận câu hỏi, sinh một query, xác minh `SELECT`, thực thi trên ontology rồi
trả cả query và câu trả lời. Ontology được mount như dữ liệu độc lập; cập nhật
literal không cần convert hay train lại model nếu schema/IRI không đổi.
