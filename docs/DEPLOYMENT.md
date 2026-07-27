# Triển khai SPARQL chatbot

## Model phát hành

Model mặc định là T5Gemma2 seed 42 vì checkpoint này có validation answer exact
cao nhất trong ba model (74,29%). Cả ba model dùng cùng seed 42; test không được
dùng để chọn checkpoint.

Checkpoint được convert sang CTranslate2 `int8_float16`; lúc chạy CPU dùng
compute type `int8`. Artifact có kích thước khoảng 397 MiB và có
`manifest.json` chứa checksum từng file.

```bash
uv run --extra train convert_sparql_model \
  --model-dir artifacts/sparql_official_v2/t5gemma2/seed-42/model \
  --output-dir artifacts/sparql_deploy_v2/t5gemma2_seed42 \
  --quantization int8_float16
```

Tokenizer T5Gemma2 được train với regex cũ của Transformers. Regex mới làm đổi
token ID của 143/936 input và 17/102 target, nên converter ghi
`gemma_legacy_regex=true` vào manifest và runtime giữ đúng chế độ đã train.

## Kiểm định sau convert

Không mặc định rằng quantization giữ nguyên output. Mỗi artifact phải được
chấm lại trên benchmark đóng băng:

```bash
uv run --extra inference evaluate_ct2_model \
  --model-dir artifacts/sparql_deploy_v2/t5gemma2_seed42 \
  --device cpu --compute-type int8 \
  --output artifacts/sparql_deploy_v2/t5gemma2_seed42/benchmark_metrics.json
```

Kết quả trên máy thử nghiệm:

| Artifact | Parse/execute | Answer exact | Canonical exact | CPU throughput |
|---|---:|---:|---:|---:|
| T5Gemma2 seed 42 | 100,00% | 77,86% | 77,86% | 3,49 câu/giây |

Artifact CTranslate2 giữ nguyên toàn bộ output đúng/sai của checkpoint
Transformers trên 140 câu; quantization không làm giảm điểm. Bằng chứng gọn
nằm tại `reports/deployment_v2.json`.

## Chạy local

```bash
uv sync --extra inference --dev
uv run --extra inference serve_sparql \
  --model-dir artifacts/sparql_deploy_v2/t5gemma2_seed42 \
  --device cpu --compute-type int8
```

Mở `http://127.0.0.1:8000`. API tối thiểu:

- `GET /healthz` → `{"status":"ok"}`;
- `POST /chat` với `{"message":"..."}` → `{"reply":"..."}`.

Luồng runtime chỉ gồm normalizer → CTranslate2 → kiểm tra `SELECT` → RDFLib →
renderer. Nếu model sinh query rỗng, sai cú pháp hoặc vi phạm giới hạn an toàn,
API trả 422; không dùng fuzzy match hay logic sửa query.

CT2 4.8.1 trên môi trường thử nghiệm tìm CUDA 12, trong khi bộ PyTorch local
dùng CUDA 13, nên lệnh phát hành mặc định chạy CPU. CTranslate2 không bắt buộc
CUDA. Chỉ bật `--device cuda` trong image/môi trường đã cung cấp đúng runtime
CUDA mà CTranslate2 yêu cầu và phải chấm lại artifact trên thiết bị đó.

## Docker và CI

Artifact CTranslate2 không commit vào Git. Upload nguyên thư mục artifact đã
kiểm định lên một model repository, rồi build:

```bash
docker build \
  --build-arg HF_REPO=owner/repository \
  --build-arg HF_REVISION=commit-sha \
  -t ontchatbot .
docker run --rm -p 8000:8000 ontchatbot
```

CI dùng repository variable `HF_CT2_REPO`, resolve commit SHA trước khi build
và ghi SHA đó vào release. Dockerfile cố ý không có model repository mặc định
để không thể vô tình phát hành artifact BARTpho/QueryPlan cũ.
