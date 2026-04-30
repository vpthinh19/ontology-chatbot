"""FastAPI web server exposing the chatbot.

Endpoints
---------
GET  /          — serves the static chat UI (``web/index.html``)
POST /chat      — JSON ``{"message": str}`` → ``{"reply": str, ...}``
GET  /healthz   — liveness probe

The server lazy-loads the heavy components (PhoBERT, ontology) on the first
request so the process starts quickly; subsequent calls hit cached singletons.
"""

from __future__ import annotations

import argparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import WEB_DIR
from ..pipeline import answer

app = FastAPI(title="Ontology-grounded Academic Chatbot", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: str
    entities: list[dict]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> JSONResponse:
    result = answer(req.message)
    return JSONResponse(result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    import uvicorn
    uvicorn.run("src.api.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
