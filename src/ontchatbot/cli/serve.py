"""Run the chatbot HTTP service."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ..runtime.agent import DEFAULT_BASE_URL, build_agent
from ..runtime.api import create_app
from ..runtime.onnx_classifier import OnnxClassifierGenerator
from ..runtime.pipeline import OntologyChatbot


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_MODEL_DIR"),
        required="ONTCHATBOT_MODEL_DIR" not in os.environ,
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default=os.environ.get("ONTCHATBOT_DEVICE", "cpu"),
    )
    parser.add_argument(
        "--log-level",
        choices=("debug", "info", "warning", "error"),
        default="info",
    )
    parser.add_argument(
        "--llm",
        default=os.environ.get("ONTCHATBOT_LLM_MODEL"),
        help="tên mô hình ngôn ngữ lớn điều phối; hoặc đặt ONTCHATBOT_LLM_MODEL",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_BASE_URL),
        help="địa chỉ máy chủ mô hình; hoặc đặt ONTCHATBOT_LLM_BASE_URL",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _build_agent(args: argparse.Namespace):
    """Dựng trợ lý: mô hình ngôn ngữ lớn điều phối, công cụ tra đồ thị.

    Khoá chỉ đọc từ môi trường và không có cờ dòng lệnh tương ứng, để nó không
    lọt vào lịch sử lệnh hay danh sách tiến trình.
    """

    if not args.llm:
        raise SystemExit(
            "chưa chỉ định mô hình ngôn ngữ lớn: dùng --llm hoặc đặt "
            "ONTCHATBOT_LLM_MODEL"
        )
    if not os.environ.get("ONTCHATBOT_LLM_API_KEY"):
        raise SystemExit("chưa đặt ONTCHATBOT_LLM_API_KEY")
    generator = OnnxClassifierGenerator.load(args.model_dir, device=args.device)
    return build_agent(
        OntologyChatbot(generator),
        model=args.llm,
        base_url=args.base_url,
    )


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc
    args = _parse_args()
    _configure_logging(args.log_level)
    uvicorn.run(
        create_app(_build_agent(args)),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
