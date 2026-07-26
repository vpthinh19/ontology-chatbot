"""Serve the ontology chatbot and bundled web UI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from ..config import PROJECT_ROOT
from ..inference import CTranslate2Generator, OntologyChatbot
from ..query_engine import SparqlError


def create_app(chatbot: OntologyChatbot, webui_dir: Path | None = None):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc

    app = FastAPI(title="NTU Ontology Chatbot", version="0.3.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat")
    def chat(payload: dict) -> dict[str, str]:
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_MODEL_DIR"),
        required="ONTCHATBOT_MODEL_DIR" not in os.environ,
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc
    args = _parse_args()
    generator = CTranslate2Generator.load(
        args.model_dir,
        device=args.device,
        compute_type=args.compute_type,
    )
    uvicorn.run(
        create_app(OntologyChatbot(generator)),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
