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
        lookup_workers,
        onnx_threads,
        budget,
        visible,
    )
    if budget > visible:
        logger.warning(
            "CPU lookup budget allows %d native threads for %d visible CPUs",
            budget,
            visible,
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_MODEL_DIR"),
        required="ONTCHATBOT_MODEL_DIR" not in os.environ,
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
    parser.add_argument(
        "--onnx-threads",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_ONNX_THREADS", "2"),
    )
    parser.add_argument(
        "--lookup-workers",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_LOOKUP_WORKERS", "4"),
    )
    return parser.parse_args(argv)


def _configure_logging(level: str) -> None:
    """Bật nhật ký, và bắt mốc thời gian nói rõ nó thuộc múi giờ nào.

    Container chạy theo múi giờ của máy chủ, thường là giờ quốc tế, còn người
    đọc nhật ký ở múi giờ khác. Không ghi độ lệch thì hai bên đọc cùng một dòng
    ra hai thời điểm cách nhau nhiều tiếng mà không ai nhận ra.
    """

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
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
    generator = OnnxClassifierGenerator.load(
        args.model_dir, intra_op_threads=args.onnx_threads
    )
    return build_agent(
        OntologyChatbot(generator),
        model=args.llm,
        base_url=args.base_url,
        lookup_workers=args.lookup_workers,
    )


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc
    args = _parse_args()
    _configure_logging(args.log_level)
    _log_cpu_budget(
        onnx_threads=args.onnx_threads, lookup_workers=args.lookup_workers
    )
    # ``log_config=None`` để máy chủ web không dựng cấu hình nhật ký riêng của
    # nó. Mặc định, các dòng của nó đi qua một khuôn khác hẳn và KHÔNG có mốc
    # thời gian, nên nhật ký trộn hai kiểu dòng: dòng của dịch vụ có giờ, dòng
    # của máy chủ web thì không. Bỏ cấu hình đó thì mọi dòng cùng một khuôn.
    uvicorn.run(
        create_app(_build_agent(args)),
        host=args.host,
        port=args.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
