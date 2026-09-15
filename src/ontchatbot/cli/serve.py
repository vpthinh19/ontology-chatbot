"""Run the chatbot HTTP service."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ..runtime.api import TurnGate, create_app
from ..settings import DEFAULT_LLM_BASE_URL, ONTOLOGY_PATH


logger = logging.getLogger(__name__)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ontology",
        type=Path,
        default=os.environ.get("ONTCHATBOT_ONTOLOGY_PATH", str(ONTOLOGY_PATH)),
        help="tệp TriG của ontology; hoặc đặt ONTCHATBOT_ONTOLOGY_PATH",
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
        default=os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        help="địa chỉ máy chủ mô hình; hoặc đặt ONTCHATBOT_LLM_BASE_URL",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument(
        "--turn-slots",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_TURN_SLOTS", "16"),
    )
    parser.add_argument(
        "--turn-queue",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_TURN_QUEUE", "64"),
    )
    parser.add_argument(
        "--search-workers",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_SEARCH_WORKERS", "4"),
        help="số luồng chạy tìm kiếm cùng lúc; hoặc đặt ONTCHATBOT_SEARCH_WORKERS",
    )
    parser.add_argument(
        "--top-k",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_SEARCH_TOP_K", "5"),
        help="số mục trả về cho mỗi lần tra; hoặc đặt ONTCHATBOT_SEARCH_TOP_K",
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


def _validate_runtime_config(args: argparse.Namespace) -> None:
    """Kiểm tra cấu hình nhẹ trước khi mở cổng, chưa nạp ontology."""

    if not args.llm:
        raise SystemExit(
            "chưa chỉ định mô hình ngôn ngữ lớn: dùng --llm hoặc đặt "
            "ONTCHATBOT_LLM_MODEL"
        )
    if not os.environ.get("ONTCHATBOT_LLM_API_KEY"):
        raise SystemExit("chưa đặt ONTCHATBOT_LLM_API_KEY")


def _build_lookup(args: argparse.Namespace):
    """Nạp ontology và dựng chỉ mục tìm kiếm trước khi máy chủ báo sẵn sàng."""

    from ..runtime.lookup import OntologyLookup
    from ..search import SearchEngine, TriGFileSource

    engine = SearchEngine.open(TriGFileSource(args.ontology), top_k=args.top_k)
    return OntologyLookup(engine, workers=args.search_workers)


def _build_instructions(lookup) -> str:
    """Lời nhắc hệ thống nêu các chủ đề đọc từ chính ontology đang phục vụ."""

    from ..runtime.agent import build_instructions, read_vocabulary

    return build_instructions(read_vocabulary(lookup.engine.ontology))


def _build_admin(args: argparse.Namespace, agent):
    """Mở trang quản trị khi có ONTCHATBOT_ADMIN_TOKEN; mỗi lần ghi, engine nạp lại tệp."""

    token = os.environ.get("ONTCHATBOT_ADMIN_TOKEN", "").strip()
    if not token:
        return None, None

    from ..admin import AdminStore, Schema
    from ..search import SearchEngine, TriGFileSource

    shapes = Path(args.ontology).with_name("shapes.ttl")

    def reload(path: Path) -> None:
        agent.lookup.engine = SearchEngine.open(TriGFileSource(path), top_k=args.top_k)
        logger.info("ontology reloaded after an admin edit path=%s", path)

    store = AdminStore(args.ontology, Schema.from_file(shapes), shapes_path=shapes, on_change=reload)
    return store, token


def _build_agent(args: argparse.Namespace):
    """Build the complete runtime before the server reports healthy."""

    import httpx

    from ..runtime.agent import MODEL_REQUEST_TIMEOUT_SECONDS, AgentLoop
    from ..runtime.api import MAX_MODEL_STEPS
    from ..runtime.llm import LightningClient

    _validate_runtime_config(args)
    lookup = _build_lookup(args)
    http = httpx.AsyncClient(
        base_url=args.base_url.rstrip("/") + "/",
        headers={
            "Authorization": f"Bearer {os.environ['ONTCHATBOT_LLM_API_KEY']}",
            "Content-Type": "application/json",
        },
        timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
    )

    async def close() -> None:
        await http.aclose()
        await lookup.aclose()

    return AgentLoop(
        LightningClient(http, model=args.llm),
        lookup,
        instructions=_build_instructions(lookup),
        max_steps=MAX_MODEL_STEPS,
        close=close,
    )


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - requires inference extra.
        raise RuntimeError("install the inference extra to serve the API") from exc
    backend_token = os.environ.get("ONTCHATBOT_BACKEND_TOKEN", "").strip()
    if not backend_token:
        raise SystemExit("chưa đặt ONTCHATBOT_BACKEND_TOKEN")
    args = _parse_args()
    _validate_runtime_config(args)
    _configure_logging(args.log_level)

    # ``log_config=None`` để máy chủ web không dựng cấu hình nhật ký riêng của
    # nó. Mặc định, các dòng của nó đi qua một khuôn khác hẳn và KHÔNG có mốc
    # thời gian, nên nhật ký trộn hai kiểu dòng: dòng của dịch vụ có giờ, dòng
    # của máy chủ web thì không. Bỏ cấu hình đó thì mọi dòng cùng một khuôn.
    agent = _build_agent(args)
    admin, admin_token = _build_admin(args, agent)
    admin_options = {"admin": admin, "admin_token": admin_token} if admin is not None else {}
    uvicorn.run(
        create_app(
            agent,
            gate=TurnGate(slots=args.turn_slots, queue_size=args.turn_queue),
            backend_token=backend_token,
            **admin_options,
        ),
        host=args.host,
        port=args.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
