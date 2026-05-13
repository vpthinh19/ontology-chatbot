# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the ontchatbot FastAPI server.
#
#   builder  → resolve + install deps + project with `uv sync --extra cpu`
#   runtime  → slim image with only the venv + source needed at request time
#
# The PhoBERT ONNX model is NOT baked in. `NerModel._resolve_onnx_path` falls
# back to ``huggingface_hub.hf_hub_download`` from ``vpthinh19/phobert-base-v2``
# on first inference, then caches it under ``$HF_HOME`` for subsequent calls.

# ---------- builder ----------
FROM python:3.14-slim AS builder

# Pull the uv binary from its official image (faster + version-pinned).
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

WORKDIR /app

# UV_LINK_MODE=copy keeps the resulting venv portable across layers (default
# is hardlink which breaks when the cache lives on a different volume than
# the destination during a multi-stage COPY).
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# Step 1 — install dependencies only (no project) so this layer is cached as
# long as pyproject.toml + uv.lock stay unchanged.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra cpu --no-dev

# Step 2 — bring in the project source and install ontchatbot itself.
COPY src/ ./src/
COPY resources/ ./resources/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra cpu --no-dev

# ---------- runtime ----------
FROM python:3.14-slim AS runtime

# uid 1000 matches the typical desktop-Linux user id so bind-mounted volumes
# from the host (e.g. ./logs) round-trip ownership cleanly.
RUN useradd --create-home --uid 1000 --shell /bin/bash ontchatbot

WORKDIR /app

COPY --from=builder --chown=ontchatbot:ontchatbot /app/.venv /app/.venv
COPY --from=builder --chown=ontchatbot:ontchatbot /app/src /app/src
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources /app/resources
COPY --chown=ontchatbot:ontchatbot webui/ /app/webui/

# Logging path used by ``configure_logging`` — writable by the app user.
RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs

# PATH brings the `serve` console script (declared in [project.scripts]) into
# scope. HF_HOME redirects model downloads under the unprivileged home so the
# first cold-start cache is persisted across container restarts when /home is
# mounted as a volume.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/ontchatbot/.cache/huggingface

USER ontchatbot
EXPOSE 8000

# start-period=120s covers the worst-case first-request cold start where
# HF Hub download (~500 MB) and ONNX Runtime session init happen lazily.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)" \
    || exit 1

# Bind to 0.0.0.0 so the container is reachable from outside; serve.py's
# argparse default is 127.0.0.1 (correct for local dev, wrong for Docker).
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
