"""FastAPI server that exposes the chatbot.

Endpoints
---------
``GET  /``         — serve the static UI (``web/index.html``)
``POST /chat``     — JSON ``{"message": str}`` → ``{"reply": str, ...}``
``GET  /healthz``  — liveness probe

The heavy components (PhoBERT, ontology) are loaded lazily on the first
request and cached as singletons; the process therefore starts quickly and
warms up on demand.

Runtime tracing — including each stage of the pipeline and the shape of the
data passing through it — is written to ``logs/chatbot.log`` (rotated) by
:mod:`ontchatbot.logging_setup`, which is initialised at server startup.
"""

from __future__ import annotations

import argparse
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ..config import WEB_DIR
from ..logging_setup import configure_logging
from ..pipeline import Pipeline

log = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    log_path = configure_logging()
    log.info("[startup] FastAPI ready log_file=%s", log_path)
    yield
    log.info("[shutdown] FastAPI stopping")


app = FastAPI(title="NTU Academic Chatbot", version="0.1.0", lifespan=_lifespan)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    greeting: bool
    entities: list[dict]


@app.middleware("http")
async def _trace_requests(request: Request, call_next):
    """Log each HTTP request with a short request id and wall-time latency."""
    rid = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    log.info("[http] rid=%s %s %s", rid, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        log.exception("[http] rid=%s unhandled exception", rid)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info("[http] rid=%s status=%s elapsed=%.1fms",
             rid, response.status_code, elapsed_ms)
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> JSONResponse:
    """Run the pipeline in a worker thread so the event loop stays free
    while PyTorch inference (blocking C++) is in flight."""
    return JSONResponse(await Pipeline.get().aanswer(req.message))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    configure_logging()
    import uvicorn
    uvicorn.run("ontchatbot.scripts.serve:app",
                host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
