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

FROM python:3.12-slim-bookworm AS runtime
RUN set -eux; apt-get update; \
    apt-get upgrade -y --no-install-recommends; \
    apt-get install -y --no-install-recommends ca-certificates; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd --system ontchatbot; \
    useradd --system --gid ontchatbot --home-dir /home/ontchatbot \
      --create-home ontchatbot
# Ảnh gốc bỏ hết .pyc của thư viện chuẩn, còn PYTHONDONTWRITEBYTECODE cấm ghi lại, nên thiếu bước
# này thì mỗi lần khởi động phải biên dịch lại asyncio, logging, importlib.metadata... từ mã nguồn.
RUN python -m compileall -q -j0 /usr/local/lib/python3.12
WORKDIR /app
COPY --from=builder --chown=ontchatbot:ontchatbot /app/.venv /app/.venv
COPY --from=builder --chown=ontchatbot:ontchatbot /app/src /app/src
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources/ontology /app/resources/ontology
RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs
# Ontology trong ảnh là bản đầu tiên. Đặt ONTCHATBOT_ONTOLOGY_GCS_URI thì lúc khởi động
# dịch vụ tải bản gốc từ Cloud Storage (chưa có thì đưa bản trong ảnh lên), và mọi lần sửa ở
# trang quản trị được ghi lên đó. Chỉ mục tìm kiếm dựng trong bộ nhớ lúc khởi động, nên ảnh
# không mang tệp dẫn xuất nào.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Ho_Chi_Minh MALLOC_ARENA_MAX=2 OPENBLAS_NUM_THREADS=1 \
    ONTCHATBOT_ONTOLOGY_PATH=/app/resources/ontology/ontology.trig \
    ONTCHATBOT_SEARCH_WORKERS=4 \
    ONTCHATBOT_TURN_SLOTS=4 ONTCHATBOT_TURN_QUEUE=8
USER ontchatbot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request,sys; port=os.environ.get('PORT','8000'); token=os.environ.get('ONTCHATBOT_BACKEND_TOKEN',''); request=urllib.request.Request(f'http://127.0.0.1:{port}/health',headers={'Authorization':f'Bearer {token}'}); sys.exit(0 if urllib.request.urlopen(request,timeout=3).status==200 else 1)" || exit 1
CMD ["serve_chatbot", "--host", "0.0.0.0"]
