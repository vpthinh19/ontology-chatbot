# Triển khai riêng tư trên Cloud Run

Runbook này triển khai một backend scale-to-zero và chỉ cho Vercel production
gọi bằng workload identity. Không tạo service-account key, không mở `allUsers` và
không yêu cầu JWT middleware trong ứng dụng.

## 1. Khai báo giá trị

Chạy trong Google Cloud Shell. Thay các giá trị trong dấu `<...>`:

```bash
export GCP_PROJECT_ID="<google-project-id>"
export REGION="asia-southeast1"
export SERVICE="ontology-chatbot"
export ARTIFACT_REPOSITORY="ontology-chatbot"
export IMAGE_TAG="<release-tag>"
export HF_REPO="vpthinh19/ntu-ontology-xlmr"
export HF_REVISION="<immutable-hugging-face-commit>"

export VERCEL_TEAM_SLUG="<team-slug>"
export VERCEL_PROJECT_NAME="<vercel-project-name>"
export POOL_ID="vercel"
export PROVIDER_ID="vercel-production"
export INVOKER_SA="vercel-cloud-run-invoker"
export RUNTIME_SA="ontology-chatbot-runtime"
export LLM_SECRET="ontology-chatbot-llm-api-key"

gcloud config set project "$GCP_PROJECT_ID"
export GCP_PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"
export INVOKER_SA_EMAIL="${INVOKER_SA}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
export RUNTIME_SA_EMAIL="${RUNTIME_SA}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
export VERCEL_ISSUER="https://oidc.vercel.com/${VERCEL_TEAM_SLUG}"
export VERCEL_AUDIENCE="https://vercel.com/${VERCEL_TEAM_SLUG}"
export VERCEL_SUBJECT="owner:${VERCEL_TEAM_SLUG}:project:${VERCEL_PROJECT_NAME}:environment:production"
export IMAGE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REPOSITORY}/ontology-chatbot:${IMAGE_TAG}"
```

`HF_REVISION` phải là commit SHA đã dùng để kiểm định model, không dùng `main`.

## 2. Tạo tài nguyên một lần

```bash
gcloud services enable \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  sts.googleapis.com

gcloud artifacts repositories create "$ARTIFACT_REPOSITORY" \
  --repository-format=docker \
  --location="$REGION"

gcloud iam service-accounts create "$INVOKER_SA" \
  --display-name="Vercel Cloud Run invoker"
gcloud iam service-accounts create "$RUNTIME_SA" \
  --display-name="Ontology chatbot runtime"

gcloud secrets create "$LLM_SECRET" --replication-policy=automatic
gcloud secrets versions add "$LLM_SECRET" --data-file=-
```

Lệnh cuối chờ dữ liệu từ stdin: dán LLM API key rồi nhấn `Ctrl-D`. Cấp cho
runtime đúng quyền đọc secret này:

```bash
gcloud secrets add-iam-policy-binding "$LLM_SECRET" \
  --member="serviceAccount:${RUNTIME_SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"
```

## 3. Tạo trust Vercel production

Trong Vercel → Project → Settings → Security, bật Secure Backend Access và chọn
issuer mode **Team**. Sau đó tạo provider tương ứng:

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --location=global \
  --display-name="Vercel"

gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --location=global \
  --workload-identity-pool="$POOL_ID" \
  --issuer-uri="$VERCEL_ISSUER" \
  --allowed-audiences="$VERCEL_AUDIENCE" \
  --attribute-mapping="google.subject=assertion.sub"

gcloud iam service-accounts add-iam-policy-binding "$INVOKER_SA_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principal://iam.googleapis.com/projects/${GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/subject/${VERCEL_SUBJECT}"
```

Binding dùng đúng một subject `environment:production`; preview và development
không thể mạo danh service account production.

## 4. Build và deploy backend

Máy build cần Docker và quyền ghi Artifact Registry:

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

Thay hai giá trị LLM nhưng giữ nguyên profile CPU/cache:

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
  --no-allow-unauthenticated \
  --set-env-vars="ONTCHATBOT_LLM_MODEL=${LLM_MODEL},ONTCHATBOT_LLM_BASE_URL=${LLM_BASE_URL},ONTCHATBOT_MODEL_REVISION=${HF_REVISION},ONTCHATBOT_ONNX_THREADS=1,ONTCHATBOT_LOOKUP_WORKERS=8,ONTCHATBOT_TURN_SLOTS=4,ONTCHATBOT_TURN_QUEUE=8,ONTCHATBOT_CLASSIFICATION_CACHE_ENTRIES=4096,ONTCHATBOT_SPARQL_CACHE_MIB=64" \
  --set-secrets="ONTCHATBOT_LLM_API_KEY=${LLM_SECRET}:latest"

export CLOUD_RUN_SERVICE_URL="$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')"

gcloud run services add-iam-policy-binding "$SERVICE" \
  --region="$REGION" \
  --member="serviceAccount:${INVOKER_SA_EMAIL}" \
  --role="roles/run.invoker"
```

Ingress phải là `all` vì Vercel ở ngoài Google Cloud; IAM vẫn chặn request trước
container. Không thêm binding `allUsers`.

## 5. Cấu hình Vercel

Đặt năm biến sau cho môi trường **Production** của project `webui`, rồi redeploy:

```text
CLOUD_RUN_SERVICE_URL=<giá trị CLOUD_RUN_SERVICE_URL ở bước 4>
GCP_PROJECT_NUMBER=<project number>
GCP_SERVICE_ACCOUNT_EMAIL=<INVOKER_SA_EMAIL>
GCP_WORKLOAD_IDENTITY_POOL_ID=vercel
GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID=vercel-production
```

Không tạo `LIGHTNING_API_TOKEN`, service-account JSON key hoặc
`VERCEL_OIDC_TOKEN` production. Vercel tự chèn assertion ngắn hạn vào request của
Function.

## 6. Kiểm tra sau deploy

Backend trực tiếp phải từ chối request không có danh tính:

```bash
curl -i "${CLOUD_RUN_SERVICE_URL}/healthz"
```

Kết quả mong đợi: `403` và không có log khởi động container mới do request bị IAM
chặn. Sau khi Vercel redeploy, kiểm tra toàn bộ đường danh tính và cold start:

```bash
curl -i "https://<production-frontend-domain>/api/healthz"
```

Kết quả mong đợi: `200` sau khoảng thời gian cold start. Trình duyệt chỉ gọi
`/api/healthz` và `/api/chat` cùng origin; không gửi Authorization và không biết
URL Cloud Run.

Nếu frontend trả `502 Could not authenticate to the backend`, kiểm tra issuer
mode Team, năm biến Vercel, subject production và binding
`roles/iam.workloadIdentityUser`. Nếu Cloud Run trả `403` qua proxy, kiểm tra
`roles/run.invoker` trên đúng service account và audience đúng bằng
`CLOUD_RUN_SERVICE_URL`.
