"""Run the chatbot HTTP service."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ..runtime.api import create_app
from ..runtime.model import CTranslate2Generator
from ..runtime.pipeline import OntologyChatbot


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_MODEL_DIR"),
        required="ONTCHATBOT_MODEL_DIR" not in os.environ,
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument(
        "--log-level",
        choices=("debug", "info", "warning", "error"),
        default="info",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _load_chatbot(args: argparse.Namespace) -> OntologyChatbot:
    generator = CTranslate2Generator.load(
        args.model_dir,
        device=args.device,
        compute_type=args.compute_type,
    )
    return OntologyChatbot(generator)


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc
    args = _parse_args()
    _configure_logging(args.log_level)
    uvicorn.run(
        create_app(_load_chatbot(args)),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
