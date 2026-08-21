"""Run the chatbot HTTP service."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ..runtime.agent import DEFAULT_BASE_URL, build_agent
from ..runtime.api import create_app
from ..runtime.aoti import AotiGenerator
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
    # Card đồ hoạ ở độ chính xác đầy đủ giữ nguyên điểm và nhanh hơn bộ xử lý
    # trung tâm; nén số nguyên 8 bit chỉ giữ được điểm khi chạy trên bộ xử lý
    # trung tâm. Đọc từ môi trường để cùng một ảnh triển khai chạy được cả hai.
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default=os.environ.get("ONTCHATBOT_DEVICE", "cpu"),
    )
    parser.add_argument(
        "--compute-type",
        default=os.environ.get("ONTCHATBOT_COMPUTE_TYPE", "int8"),
    )
    # Số lượt sinh truy vấn chạy song song. Đặt bằng số người dùng đồng thời dự
    # kiến; một người hỏi thì giá trị lớn hơn không nhanh thêm.
    parser.add_argument(
        "--inter-threads",
        type=int,
        default=int(os.environ.get("ONTCHATBOT_INTER_THREADS", "1")),
    )
    # Thư mục gói đã biên dịch sẵn. Khai thì dùng đường này thay cho đường thường:
    # cùng câu truy vấn, nhanh hơn khoảng 1,75 lần, và không cần thư viện huấn
    # luyện lúc chạy. Bỏ trống thì dùng đường thường.
    parser.add_argument(
        "--compiled-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_COMPILED_DIR"),
    )
    # Thư mục chứa bộ tách từ đi kèm gói đã biên dịch.
    parser.add_argument(
        "--compiled-tokenizer-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_COMPILED_TOKENIZER_DIR"),
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
    if args.compiled_dir:
        if not args.compiled_tokenizer_dir:
            raise SystemExit(
                "khai --compiled-dir thì phải khai cả --compiled-tokenizer-dir"
            )
        generator = AotiGenerator.load(
            args.compiled_dir, args.compiled_tokenizer_dir
        )
    else:
        generator = CTranslate2Generator.load(
            args.model_dir,
            device=args.device,
            compute_type=args.compute_type,
            inter_threads=args.inter_threads,
        )
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
