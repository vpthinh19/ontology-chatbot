"""HTTP interface for the ontology chatbot."""

from __future__ import annotations

from pathlib import Path

from ..settings import PROJECT_ROOT
from .pipeline import OntologyChatbot
from .sparql import SparqlError


def create_app(chatbot: OntologyChatbot, webui_dir: Path | None = None):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc

    app = FastAPI(title="NTU Ontology Chatbot", version="0.3.0")

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(payload: dict) -> dict[str, str]:
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            raise HTTPException(status_code=400, detail="message must be non-empty text")
        try:
            return {"reply": chatbot.answer(message)}
        except (SparqlError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="Model không tạo được truy vấn hợp lệ cho câu hỏi này.",
            ) from exc

    static_dir = webui_dir or PROJECT_ROOT / "webui"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="webui")
    return app
