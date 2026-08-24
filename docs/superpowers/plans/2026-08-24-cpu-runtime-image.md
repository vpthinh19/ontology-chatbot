# CPU ONNX Production Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a compact CPU-only production image that serves the existing FP16 ONNX classifier asynchronously on an eight-vCPU Lightning replica.

**Architecture:** One Uvicorn process owns one immutable ONNX Runtime CPU session and one read-only ontology graph. Four asynchronous lookup slots move tokenizer, inference, and SPARQL work to worker threads; each ONNX call receives two intra-op threads, giving the default replica an eight-thread native compute budget without duplicating the 572 MB model.

**Tech Stack:** Python 3.12, asyncio, ONNX Runtime CPU, FastAPI, Uvicorn, uv, Docker BuildKit, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-24-cpu-runtime-image-design.md`

## Global Constraints

- Do not modify `README.md`.
- Production and deployment are CPU-only; research and training keep their existing GPU support.
- Keep the released FP16 artifact at `vpthinh19/ntu-ontology-xlmr/onnx-xlmr`; do not quantize or replace it.
- Run one Uvicorn process with one shared ONNX session and one shared read-only ontology graph per replica.
- Default to `ONTCHATBOT_ONNX_THREADS=2` and `ONTCHATBOT_LOOKUP_WORKERS=4`.
- Keep `MAX_CONCURRENT_TURNS=4`, `MAX_QUEUED_TURNS=20`, and existing SSE/REST contracts unchanged.
- Use `python:3.12-slim-bookworm` for every Docker stage; do not manually prune or patch runtime libraries.
- Exclude CUDA, NVIDIA packages, `onnxruntime-gpu`, uv, Hugging Face tooling, compilers, tests, frontend files, documentation, and model caches from the runtime image.
- Preserve the existing uncommitted `uv.lock` upgrades for `cuda-pathfinder` 1.7.0 and `filelock` 3.32.4 when regenerating the lock.
- Bump the release version from `2.1.2` to `3.0.0`.

---

### Task 1: CPU-only ONNX session contract

**Files:**
- Modify: `src/ontchatbot/runtime/onnx_classifier.py:37-88`
- Replace tests: `tests/runtime/test_onnx_classifier.py`

**Interfaces:**
- Consumes: an exported classifier directory and optional read-only RDF graph
- Produces: `OnnxClassifierGenerator.load(model_dir: Path, *, graph: rdflib.Graph | None = None, intra_op_threads: int = 2) -> OnnxClassifierGenerator`
- Produces: a session pinned to `CPUExecutionProvider`, `ORT_SEQUENTIAL`, `ORT_ENABLE_ALL`, one inter-op thread, and the requested positive intra-op count

- [ ] **Step 1: Replace CUDA loader tests with failing CPU session-option tests**

Retain the tokenizer/model-directory fakes and add:

```python
class _SessionOptions:
    def __init__(self) -> None:
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.graph_optimization_level = None


def _cpu_ort(seen):
    def create_session(path, *, sess_options, providers):
        seen.update(path=path, options=sess_options, providers=providers)
        return SimpleNamespace(get_providers=lambda: providers)

    return SimpleNamespace(
        SessionOptions=_SessionOptions,
        ExecutionMode=SimpleNamespace(ORT_SEQUENTIAL="sequential"),
        GraphOptimizationLevel=SimpleNamespace(ORT_ENABLE_ALL="all"),
        InferenceSession=create_session,
    )


def test_load_pins_the_cpu_provider_and_two_intra_op_threads(monkeypatch, tmp_path):
    seen = {}
    _replace_model_dependencies(monkeypatch, _cpu_ort(seen))

    generator = onnx_classifier.OnnxClassifierGenerator.load(_model_dir(tmp_path))

    assert seen["providers"] == ["CPUExecutionProvider"]
    assert seen["options"].intra_op_num_threads == 2
    assert seen["options"].inter_op_num_threads == 1
    assert seen["options"].execution_mode == "sequential"
    assert seen["options"].graph_optimization_level == "all"
    assert generator.providers == ["CPUExecutionProvider"]


def test_load_accepts_an_explicit_positive_thread_count(monkeypatch, tmp_path):
    seen = {}
    _replace_model_dependencies(monkeypatch, _cpu_ort(seen))

    onnx_classifier.OnnxClassifierGenerator.load(
        _model_dir(tmp_path), intra_op_threads=3
    )

    assert seen["options"].intra_op_num_threads == 3


@pytest.mark.parametrize("threads", [0, -1])
def test_load_rejects_a_non_positive_thread_count(threads, tmp_path):
    with pytest.raises(ValueError, match="intra_op_threads must be positive"):
        onnx_classifier.OnnxClassifierGenerator.load(
            _model_dir(tmp_path), intra_op_threads=threads
        )
```

Delete the three tests for CUDA preload, the pruned CUDA flag, and GPU fallback.

- [ ] **Step 2: Run the loader tests and verify the old interface fails**

```bash
uv run pytest -n 0 tests/runtime/test_onnx_classifier.py -q
```

Expected: failures because `load()` has no `intra_op_threads`, does not pass session options, and still defaults to CUDA.

- [ ] **Step 3: Implement the CPU-only session**

Replace the device branch with:

```python
if intra_op_threads < 1:
    raise ValueError("intra_op_threads must be positive")

options = ort.SessionOptions()
options.intra_op_num_threads = intra_op_threads
options.inter_op_num_threads = 1
options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
session = ort.InferenceSession(
    str(graph_path),
    sess_options=options,
    providers=["CPUExecutionProvider"],
)
```

Remove `device`, `preload_dlls`, `disable_fallback`, and all provider fallback branches. Keep tokenization, label loading, batching, and card generation unchanged.

- [ ] **Step 4: Run focused runtime tests**

```bash
uv run pytest -n 0 tests/runtime/test_onnx_classifier.py tests/runtime/test_inference.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ontchatbot/runtime/onnx_classifier.py tests/runtime/test_onnx_classifier.py
git commit -m "Pin production inference to the CPU"
```

---

### Task 2: Bounded asynchronous lookup workers

**Files:**
- Create: `src/ontchatbot/runtime/lookup_pool.py`
- Create: `tests/runtime/test_lookup_pool.py`
- Modify: `src/ontchatbot/runtime/agent.py:278-338`
- Modify: `tests/runtime/test_agent.py:218-244`

**Interfaces:**
- Consumes: `lookup: Callable[[Sequence[str] | str], str]` and `workers: int`
- Produces: `AsyncLookupPool(lookup, workers=workers)` with `async __call__(keywords) -> str`
- Produces: `build_tool(chatbot, *, lookup_workers: int = 4)` and `build_agent(..., lookup_workers: int = 4)`

- [ ] **Step 1: Write failing concurrency and lifecycle tests**

Create `tests/runtime/test_lookup_pool.py`:

```python
from __future__ import annotations

import asyncio
import threading
import time

import httpx
import pytest

from ontchatbot.runtime.api import create_app
from ontchatbot.runtime.lookup_pool import AsyncLookupPool


def test_pool_never_runs_more_than_four_lookups_at_once() -> None:
    live = 0
    peak = 0
    lock = threading.Lock()

    def lookup(value):
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        try:
            time.sleep(0.02)
            return str(value)
        finally:
            with lock:
                live -= 1

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=4)
        return await asyncio.gather(*(pool([str(i)]) for i in range(12)))

    assert len(asyncio.run(exercise())) == 12
    assert peak == 4


def test_a_blocked_lookup_does_not_block_the_event_loop() -> None:
    started = threading.Event()
    release = threading.Event()

    def lookup(_):
        started.set()
        release.wait(timeout=1)
        return "xong"

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=1)
        task = asyncio.create_task(pool(["học phí"]))
        while not started.is_set():
            await asyncio.sleep(0)
        transport = httpx.ASGITransport(app=create_app(object()))
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await asyncio.wait_for(client.get("/healthz"), timeout=0.05)
        release.set()
        return response, await task

    response, result = asyncio.run(exercise())
    assert response.json() == {"status": "ok"}
    assert result == "xong"


def test_an_exception_releases_the_lookup_slot() -> None:
    calls = 0

    def lookup(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("hỏng")
        return "xong"

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=1)
        with pytest.raises(RuntimeError, match="hỏng"):
            await pool(["một"])
        return await asyncio.wait_for(pool(["hai"]), timeout=0.2)

    assert asyncio.run(exercise()) == "xong"


def test_cancellation_holds_the_slot_until_native_work_finishes() -> None:
    first_started = threading.Event()
    first_release = threading.Event()
    second_started = threading.Event()

    def lookup(keywords):
        if keywords == ["một"]:
            first_started.set()
            first_release.wait(timeout=1)
        else:
            second_started.set()
        return "xong"

    async def exercise():
        pool = AsyncLookupPool(lookup, workers=1)
        first = asyncio.create_task(pool(["một"]))
        while not first_started.is_set():
            await asyncio.sleep(0)
        first.cancel()
        second = asyncio.create_task(pool(["hai"]))
        await asyncio.sleep(0.02)
        assert not second_started.is_set()
        first_release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await asyncio.wait_for(second, timeout=0.2) == "xong"

    asyncio.run(exercise())


@pytest.mark.parametrize("workers", [0, -1])
def test_pool_rejects_non_positive_worker_counts(workers) -> None:
    with pytest.raises(ValueError, match="workers must be positive"):
        AsyncLookupPool(str, workers=workers)
```

- [ ] **Step 2: Run the new tests and verify collection fails**

```bash
uv run pytest -n 0 tests/runtime/test_lookup_pool.py -q
```

Expected: `ModuleNotFoundError: ontchatbot.runtime.lookup_pool`.

- [ ] **Step 3: Implement the bounded thread boundary**

Create:

```python
"""Bound synchronous ontology lookups without blocking the ASGI event loop."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence


class AsyncLookupPool:
    def __init__(self, lookup: Callable[[Sequence[str] | str], str], *, workers: int):
        if workers < 1:
            raise ValueError("workers must be positive")
        self._lookup = lookup
        self._slots = asyncio.Semaphore(workers)

    async def __call__(self, keywords: Sequence[str] | str) -> str:
        async with self._slots:
            work = asyncio.create_task(asyncio.to_thread(self._lookup, keywords))
            try:
                return await asyncio.shield(work)
            except asyncio.CancelledError:
                # Native ONNX/SPARQL work cannot be stopped by task cancellation.
                await work
                raise
```

Holding the semaphore until the native call ends prevents a disconnected request from being replaced while still consuming CPU.

- [ ] **Step 4: Make the agent tool explicitly asynchronous**

In `runtime/agent.py`:

```python
from functools import partial
from .lookup_pool import AsyncLookupPool


def build_tool(chatbot: OntologyChatbot, *, lookup_workers: int = 4):
    from agents import function_tool

    lookup = AsyncLookupPool(partial(look_up, chatbot), workers=lookup_workers)

    @function_tool(description_override=TOOL_DESCRIPTION)
    async def tra_cuu_hoc_vu(tu_khoa: list[str]) -> str:
        """Tra các chủ đề học vụ.

        Args:
            tu_khoa: Danh sách cụm từ khoá ngắn, ví dụ ["đăng ký học phần"].
        """
        return await lookup(tu_khoa)

    return tra_cuu_hoc_vu
```

Add `lookup_workers: int = 4` to `build_agent` and call `build_tool(chatbot, lookup_workers=lookup_workers)`. Update the existing client-options test to monkeypatch a keyword-aware `build_tool` fake and assert it receives `4`.

- [ ] **Step 5: Run agent, pool, API, and turn-gate tests**

```bash
uv run pytest -n 0 tests/runtime/test_lookup_pool.py tests/runtime/test_agent.py tests/runtime/test_serve.py -q
```

Expected: all tests pass, including exception/cancellation slot release, health, SSE, and the existing four-turn gate.

- [ ] **Step 6: Commit**

```bash
git add src/ontchatbot/runtime/lookup_pool.py src/ontchatbot/runtime/agent.py tests/runtime/test_lookup_pool.py tests/runtime/test_agent.py
git commit -m "Bound ontology work outside the event loop"
```

---

### Task 3: CPU serving configuration and operational CLIs

**Files:**
- Modify: `src/ontchatbot/cli/serve.py:16-102`
- Modify: `src/ontchatbot/cli/chat.py:23-74`
- Modify: `src/ontchatbot/cli/publish_classifier.py:53-120`
- Modify: `tests/runtime/test_serve_cli.py`
- Modify: `tests/research/test_export_fp16.py:85-91`

**Interfaces:**
- Consumes: `ONTCHATBOT_ONNX_THREADS` and `ONTCHATBOT_LOOKUP_WORKERS`
- Produces: `--onnx-threads` default `2`, `--lookup-workers` default `4`, both positive integers
- Produces: `_visible_cpu_count() -> int` and `_log_cpu_budget(*, onnx_threads: int, lookup_workers: int) -> None`
- Removes: `--device` and `ONTCHATBOT_DEVICE` from serving, local chat, and classifier publishing

- [ ] **Step 1: Write failing serve configuration tests**

Replace the device test and add:

```python
def test_serve_passes_cpu_limits_to_the_classifier_and_agent(monkeypatch) -> None:
    args = _parse_args(_flags("--onnx-threads", "3", "--lookup-workers", "5"))
    loaded, built = [], []
    generator = SimpleNamespace()
    monkeypatch.setenv("ONTCHATBOT_LLM_API_KEY", "khoa-thu")
    monkeypatch.setattr(
        "ontchatbot.cli.serve.OnnxClassifierGenerator.load",
        lambda path, **kwargs: loaded.append((path, kwargs)) or generator,
    )
    monkeypatch.setattr(
        "ontchatbot.cli.serve.build_agent",
        lambda chatbot, **kwargs: built.append((chatbot, kwargs)) or "tro-ly",
    )

    assert _build_agent(args) == "tro-ly"
    assert loaded == [(Path("generator"), {"intra_op_threads": 3})]
    assert built[0][1]["lookup_workers"] == 5


def test_cpu_limits_default_to_two_by_four(monkeypatch) -> None:
    monkeypatch.delenv("ONTCHATBOT_ONNX_THREADS", raising=False)
    monkeypatch.delenv("ONTCHATBOT_LOOKUP_WORKERS", raising=False)
    args = _parse_args(_flags())
    assert (args.onnx_threads, args.lookup_workers) == (2, 4)


def test_cpu_limits_can_come_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("ONTCHATBOT_ONNX_THREADS", "3")
    monkeypatch.setenv("ONTCHATBOT_LOOKUP_WORKERS", "2")
    args = _parse_args(_flags())
    assert (args.onnx_threads, args.lookup_workers) == (3, 2)


@pytest.mark.parametrize(
    ("flag", "environment"),
    [
        ("--onnx-threads", "ONTCHATBOT_ONNX_THREADS"),
        ("--lookup-workers", "ONTCHATBOT_LOOKUP_WORKERS"),
    ],
)
@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_cpu_limits_reject_invalid_values(monkeypatch, flag, environment, value):
    with pytest.raises(SystemExit):
        _parse_args(_flags(flag, value))
    monkeypatch.setenv(environment, value)
    with pytest.raises(SystemExit):
        _parse_args(_flags())


def test_removed_device_flag_is_rejected() -> None:
    with pytest.raises(SystemExit):
        _parse_args(_flags("--device", "cpu"))


def test_oversubscribed_cpu_budget_is_logged(monkeypatch, caplog) -> None:
    monkeypatch.setattr("ontchatbot.cli.serve._visible_cpu_count", lambda: 4)
    with caplog.at_level(logging.WARNING, logger="ontchatbot.cli.serve"):
        _log_cpu_budget(onnx_threads=2, lookup_workers=4)
    assert "8 native threads" in caplog.text
    assert "4 visible CPUs" in caplog.text
```

Import `_log_cpu_budget`. Include `--device` in the rejected legacy flags.

- [ ] **Step 2: Update publisher and local-chat expectations before implementation**

Change the publisher test to reject `--device cuda` while retaining the stable FP16 paths. Add an assertion using `ontchatbot.cli.chat._parse_args` that local chat rejects `--device`.

- [ ] **Step 3: Run CLI tests and verify failures**

```bash
uv run pytest -n 0 tests/runtime/test_serve_cli.py tests/research/test_export_fp16.py -q
```

Expected: failures for absent CPU flags/logger and still-supported device flags.

- [ ] **Step 4: Implement validation and CPU-budget logging**

Add:

```python
logger = logging.getLogger(__name__)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _visible_cpu_count() -> int:
    affinity = getattr(os, "sched_getaffinity", None)
    return len(affinity(0)) if affinity is not None else (os.cpu_count() or 1)


def _log_cpu_budget(*, onnx_threads: int, lookup_workers: int) -> None:
    visible = _visible_cpu_count()
    budget = onnx_threads * lookup_workers
    logger.info(
        "CPU lookup budget: %d workers x %d ONNX threads = %d native threads; "
        "%d visible CPUs",
        lookup_workers, onnx_threads, budget, visible,
    )
    if budget > visible:
        logger.warning(
            "CPU lookup budget allows %d native threads for %d visible CPUs",
            budget, visible,
        )
```

Define both new arguments with `_positive_int` and environment-backed defaults. Log the budget, load with `intra_op_threads=args.onnx_threads`, and build with `lookup_workers=args.lookup_workers`.

- [ ] **Step 5: Remove device selection from operational CLIs**

Delete `--device` from `cli/chat.py` and `cli/publish_classifier.py`. Load without a device argument. Make `kiem_do_thi_chay_duoc(model_dir)` CPU-only and print `đồ thị chạy được trên CPU`. Pass `lookup_workers=4` from local chat. Do not change research/training modules or `resources/end-to-end/measure_tool.py`.

- [ ] **Step 6: Run focused tests and commit**

```bash
uv run pytest -n 0 tests/runtime/test_serve_cli.py tests/runtime/test_agent.py tests/research/test_export_fp16.py -q
git add src/ontchatbot/cli/serve.py src/ontchatbot/cli/chat.py src/ontchatbot/cli/publish_classifier.py tests/runtime/test_serve_cli.py tests/research/test_export_fp16.py
git commit -m "Expose bounded CPU serving controls"
```

---

### Task 4: CPU inference dependencies and release version

**Files:**
- Modify: `pyproject.toml:1-58`
- Modify: `uv.lock`
- Modify: `src/ontchatbot/__init__.py:16`
- Modify: `tests/runtime/test_version.py`

**Interfaces:**
- Consumes: `uv sync --extra inference --no-dev`
- Produces: inference environment containing exactly the serving dependency families `fastapi`, `uvicorn`, `onnxruntime`, `openai-agents`, and `tokenizers`
- Produces: package/API version `3.0.0`

- [ ] **Step 1: Add a failing dependency and version contract test**

```python
import tomllib
from pathlib import Path


def test_cpu_release_version_and_inference_dependencies() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "3.0.0"
    inference = project["project"]["optional-dependencies"]["inference"]
    names = {item.split("[")[0].split(">=")[0] for item in inference}
    assert names == {"fastapi", "uvicorn", "onnxruntime", "openai-agents", "tokenizers"}
    assert ontchatbot.__version__ == "3.0.0"
```

- [ ] **Step 2: Run it and verify it fails**

```bash
uv run pytest -n 0 tests/runtime/test_version.py -q
```

Expected: failure because the project is `2.1.2` and inference contains the GPU/Hub/standard-extra dependencies.

- [ ] **Step 3: Change dependency declarations and version**

Use:

```toml
version = "3.0.0"

[project.optional-dependencies]
inference = [
    "fastapi>=0.140.0",
    "onnxruntime>=1.29.0",
    "openai-agents>=0.21.1",
    "tokenizers>=0.22.2",
    "uvicorn>=0.41.0",
]
```

Keep Hub and CPU ONNX tooling in `research`, remove the now-unnecessary inference/research conflict from `[tool.uv]`, and set `__version__ = "3.0.0"`.

- [ ] **Step 4: Regenerate the lock while preserving the user's existing upgrades**

Confirm the current diff contains `cuda-pathfinder==1.7.0` and `filelock==3.32.4`, then run:

```bash
uv lock
uv sync --frozen --extra inference --dev
```

Inspect `git diff -- uv.lock`: retain those two upgrades, change the inference edge to `onnxruntime`, and allow CUDA records reachable only through research packages to remain in the universal lock.

- [ ] **Step 5: Verify the installed production extra**

```bash
uv run python - <<'PY'
from importlib import metadata
names = {d.metadata["Name"].lower().replace("_", "-") for d in metadata.distributions()}
assert "onnxruntime" in names
assert "onnxruntime-gpu" not in names
assert "huggingface-hub" not in names
assert not {name for name in names if name.startswith("nvidia-")}
PY
uv run pytest -n 0 tests/runtime/test_version.py tests/runtime/test_onnx_classifier.py -q
```

Expected: all assertions and focused tests pass.

- [ ] **Step 6: Commit**

The same lockfile must carry both the required dependency graph and the preserved pre-existing version upgrades:

```bash
git add pyproject.toml uv.lock src/ontchatbot/__init__.py tests/runtime/test_version.py
git commit -m "Release the CPU-only runtime dependencies"
```
---

### Task 5: Slim multi-stage CPU image and verifier

**Files:**
- Modify: `Dockerfile`
- Create: `.github/scripts/verify-cpu-runtime.sh`
- Delete: `.github/scripts/verify-cuda-runtime.sh`
- Delete: `.github/scripts/prepare-runner-disk.sh`
- Delete: `tests/ci/test_prepare_runner_disk.py`
- Create: `tests/ci/test_cpu_release.py`

**Interfaces:**
- Consumes: `HF_REPO`, `HF_REVISION`, `HF_MODEL_PATH=onnx-xlmr`
- Produces: three `python:3.12-slim-bookworm` stages named `builder`, `model-fetcher`, and `runtime`
- Produces: executable `verify-cpu-runtime.sh IMAGE`

- [ ] **Step 1: Write failing structure tests**

Create `tests/ci/test_cpu_release.py`:

```python
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_dockerfile_is_cpu_only_and_uses_three_slim_stages() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    lowered = text.lower()
    assert text.count("FROM python:3.12-slim-bookworm") == 3
    for stage in ("builder", "model-fetcher", "runtime"):
        assert f" AS {stage}" in text
    assert "nvidia" not in lowered
    assert "cuda" not in lowered
    assert "ontchatbot_device" not in lowered


def test_cpu_verifier_replaces_gpu_only_scripts() -> None:
    scripts = ROOT / ".github" / "scripts"
    assert (scripts / "verify-cpu-runtime.sh").is_file()
    assert not (scripts / "verify-cuda-runtime.sh").exists()
    assert not (scripts / "prepare-runner-disk.sh").exists()
```

- [ ] **Step 2: Verify the tests fail**

```bash
uv run pytest -n 0 tests/ci/test_cpu_release.py -q
```

Expected: Docker still uses NVIDIA and the new verifier is absent.

- [ ] **Step 3: Rewrite the Docker stages**

Use these exact stage responsibilities:

```dockerfile
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --python /usr/local/bin/python \
      --no-install-project --extra inference --no-dev
COPY src/ ./src/
COPY resources/ ./resources/
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
COPY --from=builder --chown=ontchatbot:ontchatbot /app/resources /app/resources
COPY --from=model-fetcher --chown=ontchatbot:ontchatbot /app/model /app/model
RUN mkdir -p /app/logs && chown ontchatbot:ontchatbot /app/logs
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Ho_Chi_Minh MALLOC_ARENA_MAX=2 \
    ONTCHATBOT_ONNX_THREADS=2 ONTCHATBOT_LOOKUP_WORKERS=4
USER ontchatbot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3).status==200 else 1)" || exit 1
CMD ["serve_sparql", "--model-dir", "/app/model", "--host", "0.0.0.0", "--port", "8000"]
```

The builder may read `README.md` because package metadata names it, but the file must not be edited and is not copied into runtime. Hub runs only in the isolated model-fetch command; do not put it in `/app/.venv`.

- [ ] **Step 4: Add the CPU verifier and remove GPU cleanup**

Create mode-0755 `.github/scripts/verify-cpu-runtime.sh`:

```sh
#!/bin/sh
set -eu
image=${1:?usage: verify-cpu-runtime.sh IMAGE}

docker run --rm --entrypoint /bin/sh "$image" -c '
set -eu
test -z "${CUDA_VERSION:-}"
test ! -e /app/cuda
test ! -d /app/.venv/lib/python3.12/site-packages/nvidia
! command -v uv >/dev/null 2>&1
python - <<"PY"
import importlib.util
import sys
from importlib import metadata
from pathlib import Path

assert sys.version_info[:2] == (3, 12)
names = {d.metadata["Name"].lower().replace("_", "-") for d in metadata.distributions()}
assert "onnxruntime" in names
assert "onnxruntime-gpu" not in names
assert not {name for name in names if name.startswith("nvidia-")}
assert importlib.util.find_spec("huggingface_hub") is None

from ontchatbot.runtime.onnx_classifier import OnnxClassifierGenerator
generator = OnnxClassifierGenerator.load(Path("/app/model"), intra_op_threads=2)
assert generator.providers == ["CPUExecutionProvider"]
assert generator.generate("điều kiện xét học bổng")
PY
'
```

Delete the two GPU-only scripts and `test_prepare_runner_disk.py`.

- [ ] **Step 5: Build and verify the real image**

```bash
HF_REVISION=$(curl -sf https://huggingface.co/api/models/vpthinh19/ntu-ontology-xlmr | jq -r .sha)
test -n "$HF_REVISION" && test "$HF_REVISION" != null
uv run pytest -n 0 tests/ci/test_cpu_release.py -q
docker build --build-arg HF_REPO=vpthinh19/ntu-ontology-xlmr \
  --build-arg HF_REVISION="$HF_REVISION" -t ontchatbot:cpu-local .
sh .github/scripts/verify-cpu-runtime.sh ontchatbot:cpu-local
```

Expected: structure tests pass and the real classifier runs through CPU only.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile .github/scripts tests/ci
git commit -m "Build the service on the CPU runtime"
```

---

### Task 6: CPU release workflow and size evidence

**Files:**
- Modify: `.github/workflows/ci.yml:84-208`
- Modify: `tests/ci/test_cpu_release.py`

**Interfaces:**
- Consumes: `verify-cpu-runtime.sh IMAGE`
- Produces: release jobs that measure, verify, smoke-test, scan, and push the CPU image

- [ ] **Step 1: Add a failing workflow contract test**

```python
def test_release_workflow_measures_and_verifies_the_cpu_image() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "prepare-runner-disk.sh" not in text
    assert "verify-cuda-runtime.sh" not in text
    assert "ONTCHATBOT_DEVICE" not in text
    assert "verify-cpu-runtime.sh" in text
    assert "docker image inspect --format '{{.Size}}'" in text
    assert "docker history --no-trunc" in text
    assert "cuda image" not in text.lower()
```

- [ ] **Step 2: Verify it fails**

```bash
uv run pytest -n 0 tests/ci/test_cpu_release.py::test_release_workflow_measures_and_verifies_the_cpu_image -q
```

- [ ] **Step 3: Replace the GPU release steps**

Remove runner cleanup and post-build BuildKit pruning, set `cache-to: type=gha,mode=max`, remove the smoke-test device environment, and add:

```yaml
      - name: Record image size and layers
        run: |
          BYTES=$(docker image inspect --format '{{.Size}}' "$IMAGE:$VERSION")
          echo "Uncompressed image bytes: $BYTES"
          docker history --no-trunc "$IMAGE:$VERSION"
          docker system df
          df -h /

      - name: Verify the CPU runtime
        run: sh .github/scripts/verify-cpu-runtime.sh "$IMAGE:$VERSION"
```

Keep the 120-second health loop, Trivy OS scan, immutable tag, `latest`, Hub revision, and GitHub release behavior.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest -n 0 tests/ci -q
sh -n .github/scripts/verify-cpu-runtime.sh
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml", aliases: true)'
git add .github/workflows/ci.yml tests/ci/test_cpu_release.py
git commit -m "Measure and verify the CPU release image"
```

Expected: tests and syntax checks pass.

---

### Task 7: Full production verification

**Files:**
- Verify only: tracked source, tests, Docker, workflow, and frontend
- Do not modify: `README.md`
- Do not add: local models, benchmark output, `webui/dist`, browser results, logs, or session files

**Interfaces:**
- Consumes: Tasks 1-6 and `ontchatbot:cpu-local`
- Produces: complete tests, 390-question equivalence, startup, size, and scope evidence

- [ ] **Step 1: Run all backend and frontend checks**

```bash
uv sync --frozen --extra inference --dev
uv run pytest -q
npm --prefix webui ci
npm --prefix webui test
npm --prefix webui run build
```

- [ ] **Step 2: Evaluate all 390 questions through CPU ONNX**

```bash
uv run python - <<'PY'
import json
import time
import asyncio
from pathlib import Path
from ontchatbot.runtime.cards import CardLookup
from ontchatbot.runtime.lookup_pool import AsyncLookupPool
from ontchatbot.runtime.onnx_classifier import OnnxClassifierGenerator
from ontchatbot.runtime.pipeline import OntologyChatbot

rows = [json.loads(line) for line in Path("resources/dataset/test.jsonl").read_text().splitlines() if line]
lookup = CardLookup()
generator = OnnxClassifierGenerator.load(
    Path("artifacts/entity-linking/onnx-xlmr"), intra_op_threads=2
)
started = time.perf_counter()
predictions = []
for offset in range(0, len(rows), 16):
    batch = rows[offset:offset + 16]
    predictions.extend(generator.generate_many([row["input"] for row in batch]))
expected = [lookup.query(row["query_id"], row["target"]) for row in rows]
correct = sum(a == b for a, b in zip(predictions, expected, strict=True))
elapsed = time.perf_counter() - started
assert len(rows) == 390
assert correct == 390, f"{correct}/390 exact"
assert generator.providers == ["CPUExecutionProvider"]

chatbot = OntologyChatbot(generator)
questions = [row["input"] for row in rows[:20]]
stable = [chatbot.answer_many([question]) for question in questions]

async def verify_shared_runtime():
    pool = AsyncLookupPool(chatbot.answer_many, workers=4)
    return await asyncio.gather(*(pool([question]) for question in questions))

assert asyncio.run(verify_shared_runtime()) == stable
print(f"CPU FP16: 390/390 exact, {elapsed:.3f}s, {390 / elapsed:.1f} questions/s")
PY
```

Expected: `390/390 exact`, followed by 20 stable concurrent results sharing the
same session and graph, without writing a tracked artifact.

- [ ] **Step 3: Smoke-test startup**

```bash
CONTAINER=ontchatbot-cpu-final
docker run -d --name "$CONTAINER" \
  -e ONTCHATBOT_LLM_MODEL=smoke-test \
  -e ONTCHATBOT_LLM_API_KEY=smoke-test \
  -p 127.0.0.1:8000:8000 ontchatbot:cpu-local
started=$(date +%s)
until curl -fsS http://127.0.0.1:8000/healthz >/dev/null; do
  docker inspect --format '{{.State.Running}}' "$CONTAINER" | grep -qx true
  test $(( $(date +%s) - started )) -lt 120
  sleep 1
done
echo "healthz ready after $(( $(date +%s) - started ))s"
docker logs "$CONTAINER"
docker rm -f "$CONTAINER"
```

- [ ] **Step 4: Record image and scope evidence**

```bash
docker image inspect --format 'uncompressed={{.Size}} bytes' ontchatbot:cpu-local
docker history --no-trunc ontchatbot:cpu-local
sh .github/scripts/verify-cpu-runtime.sh ontchatbot:cpu-local
! rg -n -i 'cuda|nvidia|onnxruntime-gpu|ONTCHATBOT_DEVICE|--device' \
  Dockerfile pyproject.toml src/ontchatbot/runtime src/ontchatbot/cli/serve.py \
  src/ontchatbot/cli/chat.py src/ontchatbot/cli/publish_classifier.py \
  .github/workflows/ci.yml
rg -n 'torch\.cuda|autocast\("cuda"' src/ontchatbot/research/classifier.py
```

Expected: production scan is empty and the research scan still finds GPU training. Report uncompressed local size; only report compressed size after Docker Hub provides it.

- [ ] **Step 5: Check cleanliness and README immutability**

```bash
git diff --check
git diff -- README.md
git status --short
git log --oneline --decorate -8
```

Expected: README diff is empty and no `:memory:.ses`, model, log, build, browser, or benchmark output appears.

- [ ] **Step 6: Verify before claiming completion**

Use `superpowers:verification-before-completion` and cite exact test, image, and 390-question outputs.
