# Triển khai Cloud Run với Vercel proxy

Backend scale-to-zero và cho phép request ở tầng Cloud Run IAM, nhưng `/health`
và `/chat` chỉ nhận bearer token bí mật do Vercel Function chèn vào. Token không
được gửi xuống trình duyệt.

## 1. Khai báo

```bash
export GCP_PROJECT_ID="ontology-chatbot-1"
export REGION="asia-southeast1"
export SERVICE="ontology-chatbot"
export ARTIFACT_REPOSITORY="ontology-chatbot"
export IMAGE_TAG="<release-tag>"
export HF_REPO="vpthinh19/ntu-ontology-xlmr"
export HF_REVISION="<immutable-hugging-face-commit>"
export RUNTIME_SA="ontology-chatbot-runtime"
export LLM_SECRET="ontology-chatbot-llm-api-key"
export BACKEND_SECRET="ontology-chatbot-backend-token"

gcloud config set project "$GCP_PROJECT_ID"
export RUNTIME_SA_EMAIL="${RUNTIME_SA}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
export IMAGE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REPOSITORY}/ontology-chatbot:${IMAGE_TAG}"
```

`HF_REVISION` phải là commit SHA đã kiểm định, không dùng `main`.

## 2. Tạo token một lần

Không in token vào shell history hoặc commit nó. Lệnh sau tạo 32 byte ngẫu nhiên
và đưa thẳng vào Secret Manager:

```bash
openssl rand -base64 32 | tr -d '\n' | \
  gcloud secrets create "$BACKEND_SECRET" \
    --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding "$BACKEND_SECRET" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

Nếu secret đã tồn tại và cần xoay token, dùng `gcloud secrets versions add`
thay cho `gcloud secrets create`.

## 3. Build image

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"

docker build \
  --build-arg "HF_REPO=${HF_REPO}" \
  --build-arg "HF_REVISION=${HF_REVISION}" \
  --build-arg "HF_MODEL_PATH=onnx-xlmr" \
  --tag "$IMAGE" \
  .
docker push "$IMAGE"
```

## 4. Deploy backend

```bash
export LLM_MODEL="<llm-model-name>"
export LLM_BASE_URL="<openai-compatible-base-url>"

gcloud run deploy "$SERVICE" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$RUNTIME_SA_EMAIL" \
  --cpu=1 \
  --memory=1536Mi \
  --concurrency=4 \
  --min-instances=0 \
  --max-instances=3 \
  --cpu-throttling \
  --cpu-boost \
  --timeout=300s \
  --port=8080 \
  --ingress=all \
  --no-invoker-iam-check \
  --set-env-vars="ONTCHATBOT_LLM_MODEL=${LLM_MODEL},ONTCHATBOT_LLM_BASE_URL=${LLM_BASE_URL},ONTCHATBOT_MODEL_REVISION=${HF_REVISION},ONTCHATBOT_ONNX_THREADS=1,ONTCHATBOT_LOOKUP_WORKERS=8,ONTCHATBOT_TURN_SLOTS=4,ONTCHATBOT_TURN_QUEUE=8,ONTCHATBOT_CLASSIFICATION_CACHE_ENTRIES=4096,ONTCHATBOT_SPARQL_CACHE_MIB=64" \
  --set-secrets="ONTCHATBOT_LLM_API_KEY=${LLM_SECRET}:latest,ONTCHATBOT_BACKEND_TOKEN=${BACKEND_SECRET}:latest"

export CLOUD_RUN_SERVICE_URL="$(gcloud run services describe "$SERVICE" \
  --region="$REGION" --format='value(status.url)')"
```

## 5. Cấu hình Vercel

Trong project Vercel, đặt hai biến cho môi trường Production rồi redeploy:

```text
CLOUD_RUN_SERVICE_URL=<giá trị CLOUD_RUN_SERVICE_URL ở bước 4>
BACKEND_API_TOKEN=<giá trị secret ở lệnh dưới>
```

Lấy token để dán vào Vercel mà không ghi nó vào repository:

```bash
gcloud secrets versions access latest --secret="$BACKEND_SECRET"
```

Xoá các biến OIDC cũ (`GCP_PROJECT_NUMBER`, `GCP_SERVICE_ACCOUNT_EMAIL`,
`GCP_WORKLOAD_IDENTITY_POOL_ID`, `GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID`) sau
khi xác nhận production hoạt động. `webui/vercel.json` đặt Function tại `sin1`.

## 6. Kiểm tra

Không token và token sai phải nhận `401`; token đúng phải nhận `200`:

```bash
curl -i "$CLOUD_RUN_SERVICE_URL/health"
curl -i -H 'Authorization: Bearer wrong' "$CLOUD_RUN_SERVICE_URL/health"
curl -i -H "Authorization: Bearer $(gcloud secrets versions access latest --secret="$BACKEND_SECRET")" \
  "$CLOUD_RUN_SERVICE_URL/health"
curl -i "https://<production-frontend-domain>/api/healthz"
```

Trình duyệt chỉ gọi `/api/healthz` và `/api/chat` cùng origin. IAM public ở đây
không đồng nghĩa API mở: ứng dụng vẫn kiểm token bằng phép so sánh constant-time.
Request rác có thể đánh thức instance scale-to-zero, nhưng không vượt qua `/chat`.
