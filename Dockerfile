# syntax=docker/dockerfile:1

# ---------- builder ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/
WORKDIR /app

# UV_LINK_MODE=copy giữ venv portable khi COPY qua stage; tắt tải python (dùng python của image).
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra inference --no-dev

COPY src/ ./src/
COPY resources/ ./resources/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra inference --no-dev

# Chỉ tải artifact CTranslate2 dùng khi inference. Checkpoint Transformers và
# báo cáo benchmark cùng repository không được đưa vào runtime image.
ARG HF_REPO=
ARG HF_REVISION=main
RUN test -n "${HF_REPO}" && \
    /app/.venv/bin/python -c "from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='${HF_REPO}', revision='${HF_REVISION}', \
local_dir='/app/hf-model', allow_patterns=['ctranslate2/*'])"


# ---------- runtime ----------
FROM python:3.12-slim AS runtime

# tạo user với home dir
RUN useradd --create-home --uid 1000 --shell /bin/bash ontchatbot
WORKDIR /app

COPY --from=builder --chown=ontchatbot:ontchatbot /app/.venv /app/.venv
COPY --from=builder --chown=ontchatbot:ontchatbot /app/src /app/src
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources /app/resources
COPY --from=builder --chown=ontchatbot:ontchatbot /app/hf-model/ctranslate2 /app/model
COPY --chown=ontchatbot:ontchatbot webui/ /app/webui/

RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs

# PATH đưa venv lên đầu (uvicorn, python của venv).
# HF_HUB_OFFLINE=1 vì model đã tải sẵn, ko gọi ra internet
# MALLOC_ARENA_MAX=2 giảm RSS ~50-100MB ở tải "1 request tại một thời điểm".
# ONTCHATBOT_DEVICE / ONTCHATBOT_COMPUTE_TYPE chọn nơi chạy mô hình sinh truy vấn.
# Mặc định là bộ xử lý trung tâm để ảnh chạy được trên máy không có card đồ hoạ.
# Trên máy có card, đặt ONTCHATBOT_DEVICE=cuda và ONTCHATBOT_COMPUTE_TYPE=float32
# rồi chạy container với quyền dùng card: cùng điểm số, nhanh hơn khoảng 1,5 lần.
# Nén số nguyên 8 bit chỉ giữ nguyên điểm trên bộ xử lý trung tâm.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    MALLOC_ARENA_MAX=2 \
    ONTCHATBOT_DEVICE=cpu \
    ONTCHATBOT_COMPUTE_TYPE=int8 \
    ONTCHATBOT_INTER_THREADS=1

USER ontchatbot
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)" \
    || exit 1

CMD ["serve_sparql", "--model-dir", "/app/model", "--host", "0.0.0.0", "--port", "8000"]
