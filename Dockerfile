# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --python /usr/local/bin/python \
      --no-install-project --extra inference --no-dev
COPY src/ ./src/
COPY resources/ontology/ ./resources/ontology/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --python /usr/local/bin/python --extra inference --no-dev

FROM python:3.12-slim-bookworm AS model-fetcher
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
WORKDIR /app
ARG HF_REPO
ARG HF_REVISION=main
ARG HF_MODEL_PATH=onnx-xlmr
RUN --mount=type=cache,target=/root/.cache/uv \
    test -n "$HF_REPO" && \
    uv run --no-project --with "huggingface-hub>=1.4,<2" python -c \
    "import shutil; from pathlib import Path; \
from huggingface_hub import snapshot_download; \
root=Path('/app/hf-model'); path='$HF_MODEL_PATH'; \
snapshot_download(repo_id='$HF_REPO', revision='$HF_REVISION', \
local_dir=root, allow_patterns=[path + '/*']); \
shutil.copytree(root / path, '/app/model')"

FROM python:3.12-slim-bookworm AS runtime
RUN set -eux; apt-get update; \
    apt-get upgrade -y --no-install-recommends; \
    apt-get install -y --no-install-recommends ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd --system ontchatbot; \
    useradd --system --gid ontchatbot --home-dir /home/ontchatbot \
      --create-home ontchatbot
WORKDIR /app
COPY --from=builder --chown=ontchatbot:ontchatbot /app/.venv /app/.venv
COPY --from=builder --chown=ontchatbot:ontchatbot /app/src /app/src
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources/ontology /app/resources/ontology
COPY --from=model-fetcher --chown=ontchatbot:ontchatbot /app/model /app/model
RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Ho_Chi_Minh MALLOC_ARENA_MAX=2 \
    ONTCHATBOT_ONNX_THREADS=1 ONTCHATBOT_LOOKUP_WORKERS=8 \
    ONTCHATBOT_TURN_SLOTS=4 ONTCHATBOT_TURN_QUEUE=8
USER ontchatbot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request,sys; port=os.environ.get('PORT','8000'); token=os.environ.get('ONTCHATBOT_BACKEND_TOKEN',''); request=urllib.request.Request(f'http://127.0.0.1:{port}/health',headers={'Authorization':f'Bearer {token}'}); sys.exit(0 if urllib.request.urlopen(request,timeout=3).status==200 else 1)" || exit 1
CMD ["serve_sparql", "--model-dir", "/app/model", "--host", "0.0.0.0"]
