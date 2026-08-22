# syntax=docker/dockerfile:1

# ---------- builder ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/
WORKDIR /app

# Sao chép thay vì liên kết cứng để môi trường ảo còn dùng được sau khi COPY sang
# tầng runtime; dùng Python của image thay vì tải bản khác.
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

# Chỉ tải đồ thị ONNX của bộ phân loại được chọn. Các model còn lại và kết quả
# benchmark nằm cùng kho phát hành nhưng không thuộc ảnh chạy.
#
# Đồ thị này khép kín: nó mang sẵn trọng số đã hoà bộ điều hợp, kèm bộ tách từ và
# bảng nhãn. Không phải tải bộ mã hoá nền, và lúc chạy không ra mạng.
ARG HF_REPO=
ARG HF_REVISION=main
ARG HF_MODEL_PATH=onnx-xlmr
RUN test -n "${HF_REPO}" && \
    /app/.venv/bin/python -c "import shutil; from pathlib import Path; \
from huggingface_hub import snapshot_download; \
root=Path('/app/hf-model'); path='${HF_MODEL_PATH}'; \
snapshot_download(repo_id='${HF_REPO}', revision='${HF_REVISION}', \
local_dir=root, allow_patterns=[path + '/*']); \
shutil.copytree(root / path, '/app/classifier-model')"


# ---------- runtime ----------
FROM python:3.12-slim AS runtime

# Chạy dưới người dùng thường, có thư mục nhà để các thư viện ghi cache tạm.
RUN useradd --create-home --uid 1000 --shell /bin/bash ontchatbot
WORKDIR /app

COPY --from=builder --chown=ontchatbot:ontchatbot /app/.venv /app/.venv
COPY --from=builder --chown=ontchatbot:ontchatbot /app/src /app/src
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources /app/resources
COPY --from=builder --chown=ontchatbot:ontchatbot /app/classifier-model /app/model
COPY --chown=ontchatbot:ontchatbot webui/ /app/webui/

RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs

# PATH đặt môi trường ảo lên đầu. Chế độ ngoại tuyến vì model đã nằm trong ảnh,
# không lượt chạy nào được ra mạng. Giới hạn vùng cấp phát bộ nhớ giảm khoảng
# 50-100 MB thường trú ở mức tải một yêu cầu tại một thời điểm.
#
# Mặc định chạy trên card đồ hoạ: ảnh này dựng để triển khai trên máy chủ có card,
# và card được cấp thẳng vào container. Chạy thử trên máy cá nhân thì cần cờ
# ``--gpus all``; máy không có card thì đặt ONTCHATBOT_DEVICE=cpu.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    MALLOC_ARENA_MAX=2 \
    ONTCHATBOT_DEVICE=cuda

USER ontchatbot
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)" \
    || exit 1

CMD ["serve_sparql", "--model-dir", "/app/model", "--host", "0.0.0.0", "--port", "8000"]
