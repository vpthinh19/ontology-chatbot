"""Chạy dịch vụ hỏi đáp qua HTTP."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ..runtime.service import Config, Service
from ..settings import DEFAULT_LLM_BASE_URL, ONTOLOGY_PATH


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    env = os.environ.get
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", type=Path, default=env("ONTCHATBOT_ONTOLOGY_PATH", str(ONTOLOGY_PATH)),
                        help="tệp TriG của ontology; hoặc đặt ONTCHATBOT_ONTOLOGY_PATH")
    parser.add_argument("--log-level", choices=("debug", "info", "warning", "error"), default="info")
    parser.add_argument("--llm", default=env("ONTCHATBOT_LLM_MODEL"),
                        help="tên mô hình ngôn ngữ lớn; hoặc đặt ONTCHATBOT_LLM_MODEL")
    parser.add_argument("--base-url", default=env("ONTCHATBOT_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
                        help="địa chỉ máy chủ mô hình; hoặc đặt ONTCHATBOT_LLM_BASE_URL")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(env("PORT", "8000")))
    parser.add_argument("--turn-slots", type=_positive_int, default=env("ONTCHATBOT_TURN_SLOTS", "16"),
                        help="số lượt trả lời chạy cùng lúc; hoặc đặt ONTCHATBOT_TURN_SLOTS")
    parser.add_argument("--turn-queue", type=_positive_int, default=env("ONTCHATBOT_TURN_QUEUE", "64"),
                        help="số lượt được xếp hàng chờ; hoặc đặt ONTCHATBOT_TURN_QUEUE")
    parser.add_argument("--search-workers", type=_positive_int, default=env("ONTCHATBOT_SEARCH_WORKERS", "4"),
                        help="số luồng chạy tìm kiếm cùng lúc; hoặc đặt ONTCHATBOT_SEARCH_WORKERS")
    parser.add_argument("--top-k", type=_positive_int, default=env("ONTCHATBOT_SEARCH_TOP_K", "5"),
                        help="số mục trả về cho mỗi lần tra; hoặc đặt ONTCHATBOT_SEARCH_TOP_K")
    parser.add_argument("--refresh-seconds", type=_positive_int,
                        default=env("ONTCHATBOT_ONTOLOGY_REFRESH_SECONDS", "60"),
                        help="chu kỳ hỏi Cloud Storage xem có bản mới; hoặc đặt ONTCHATBOT_ONTOLOGY_REFRESH_SECONDS")
    return parser.parse_args(argv)


def _config(args: argparse.Namespace) -> Config:
    return Config.from_env(
        ontology=Path(args.ontology), llm_model=args.llm or "", llm_base_url=args.base_url,
        turn_slots=args.turn_slots, turn_queue=args.turn_queue, search_workers=args.search_workers,
        top_k=args.top_k, refresh_seconds=args.refresh_seconds,
    )


def _configure_logging(level: str) -> None:
    """Mốc thời gian kèm múi giờ: container thường chạy giờ quốc tế, người đọc ở múi giờ khác."""

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
    )


def main() -> None:
    import uvicorn

    args = _parse_args()
    config = _config(args)
    if not config.backend_token:
        raise SystemExit("chưa đặt ONTCHATBOT_BACKEND_TOKEN")
    config.check_llm()
    _configure_logging(args.log_level)
    service = Service(config).start()
    # log_config=None: dòng nhật ký của uvicorn đi qua cùng khuôn (có mốc thời gian) với dịch vụ.
    uvicorn.run(service.app(), host=args.host, port=args.port, log_config=None)


if __name__ == "__main__":
    main()
