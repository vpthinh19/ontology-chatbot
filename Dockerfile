# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the ontchatbot FastAPI server.
#
#   builder  → resolve + install deps + project with `uv sync --extra inference`
#   runtime  → slim image with only the venv + source needed at request time
#
# The ``inference`` extra (pyproject.toml) is deliberately tiny — only
# onnxruntime CPU on top of the core deps. No torch, no datasets, no plotting.
# This keeps the runtime image's resident memory under Render's free-tier
# 512 MB cap. Training / evaluation deps live under the ``train`` extra and
# are NOT installed here.
#
# The PhoBERT ONNX (INT8) model is baked into the image at the
# ``snapshot_download`` step below — first inference does not hit HF Hub.

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
    uv sync --frozen --no-install-project --extra inference --no-dev

# Step 2 — bring in the project source and install ontchatbot itself.
COPY src/ ./src/
COPY resources/ ./resources/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra inference --no-dev

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

# Pre-create the HF Hub cache so the first cold-start ``from_pretrained`` does
# not have to mkdir it lazily under the unprivileged user. ``useradd
# --create-home`` builds /home/ontchatbot but leaves the .cache subtree
# absent, so without this, huggingface_hub dies with PermissionError before
# the first network request — even though it would have written into a
# directory the user technically owns. Kept as defensive fallback even
# though the baked model below removes the runtime HF Hub dependency.
RUN mkdir -p /home/ontchatbot/.cache/huggingface && \
    chown -R ontchatbot:ontchatbot /home/ontchatbot/.cache

# Bake the fine-tuned NER model into the image so cold-start does not depend
# on HF Hub availability and the first /chat reply lands in seconds instead
# of minutes. Pinning the revision via ARG keeps this layer cacheable across
# code edits — bump it with --build-arg MODEL_REVISION=<sha> after pushing a
# new quantized checkpoint. NerModel.__init__ checks if MODEL_DIR is a
# local directory first, so the baked files are used without any HF Hub
# round-trip at request time.
ARG MODEL_REVISION=main
RUN /app/.venv/bin/python -c "from huggingface_hub import snapshot_download; \
snapshot_download(repo_id='vpthinh19/phobert-base-v2', revision='${MODEL_REVISION}', \
local_dir='/app/artifacts/models/phobert_ner_ft', \
allow_patterns=['*.json', '*.txt', '*.codes', 'model.onnx*'])" \
    && chown -R ontchatbot:ontchatbot /app/artifacts

# PATH brings the `serve` console script (declared in [project.scripts]) into
# scope. HF_HOME redirects model downloads under the unprivileged home so the
# first cold-start cache is persisted across container restarts when /home is
# mounted as a volume.
#
# Memory tuning for low-RAM hosts (Render free tier = 512 MB):
#   MALLOC_ARENA_MAX=2 — glibc by default reserves 8×NCPU malloc arenas;
#                       each holds memory across free() calls and fragments
#                       heavily on multi-threaded apps. Capping at 2 drops
#                       RSS by ~50-100 MB on typical FastAPI + ORT workloads
#                       with no measurable latency impact at our 1-req-at-a-
#                       time traffic profile.
#   HF_HUB_DISABLE_TELEMETRY=1 — kills the background HEAD request HF Hub
#                       fires on import; tiny RAM win but also one less
#                       network dependency at cold-start.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/ontchatbot/.cache/huggingface \
    MALLOC_ARENA_MAX=2 \
    HF_HUB_DISABLE_TELEMETRY=1

USER ontchatbot
EXPOSE 8000

# start-period=300s is a defensive ceiling: with the model baked in (above),
# cold-start is just ORT session init (~10 s) and the first request lands
# fast; without baking (e.g. an override build), cold-start re-downloads
# ~130 MB INT8 + tokenizer files, which can take minutes on a constrained
# uplink. The longer start-period absorbs both scenarios without flapping.
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
    CMD python -c "import urllib.request, sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200 else 1)" \
    || exit 1

# Bind to 0.0.0.0 so the container is reachable from outside; serve.py's
# argparse default is 127.0.0.1 (correct for local dev, wrong for Docker).
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
