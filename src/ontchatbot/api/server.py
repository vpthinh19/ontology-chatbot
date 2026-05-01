"""FastAPI server that exposes the chatbot.

Endpoints
---------
``GET  /``         — serve the static UI (``web/index.html``)
``POST /chat``     — JSON ``{"message": str}`` → ``{"reply": str, ...}``
``GET  /healthz``  — liveness probe

The heavy components (PhoBERT, ontology) are loaded lazily on the first
request and cached as singletons; the process therefore starts quickly and
warms up on demand.
"""

from __future__ import annotations

import argparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ..config import WEB_DIR
from ..pipeline import answer

app = FastAPI(title="NTU Academic Chatbot", version="0.1.0")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    greeting: bool
    entities: list[dict]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> JSONResponse:
    return JSONResponse(answer(req.message))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("ontchatbot.api.server:app",
                host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
