"""Run the chatbot HTTP service."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import logging
import os
from pathlib import Path

from ..runtime.api import TurnGate, create_app
from ..settings import DEFAULT_LLM_BASE_URL


logger = logging.getLogger(__name__)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from None
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
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
        "--onnx-threads",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_ONNX_THREADS", "1"),
    )
    parser.add_argument(
        "--lookup-workers",
        type=_positive_int,
        default=os.environ.get("ONTCHATBOT_LOOKUP_WORKERS", "8"),
    )
    parser.add_argument(
        "--classification-cache-entries",
        type=_non_negative_int,
        default=os.environ.get("ONTCHATBOT_CLASSIFICATION_CACHE_ENTRIES", "4096"),
    )
    parser.add_argument(
        "--sparql-cache-mib",
        type=_non_negative_int,
        default=os.environ.get("ONTCHATBOT_SPARQL_CACHE_MIB", "64"),
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
    """Kiểm tra cấu hình nhẹ trước khi mở cổng, chưa nạp model hay ontology."""

    if not args.llm:
        raise SystemExit(
            "chưa chỉ định mô hình ngôn ngữ lớn: dùng --llm hoặc đặt "
            "ONTCHATBOT_LLM_MODEL"
        )
    if not os.environ.get("ONTCHATBOT_LLM_API_KEY"):
        raise SystemExit("chưa đặt ONTCHATBOT_LLM_API_KEY")


def _build_agent(args: argparse.Namespace):
    """Build the complete runtime before the server reports healthy."""

    import httpx

    from ..runtime.agent import (
        MODEL_REQUEST_TIMEOUT_SECONDS,
        AgentLoop,
        build_instructions,
        look_up_async,
    )
    from ..runtime.api import MAX_MODEL_STEPS
    from ..runtime.llm import LightningClient

    _validate_runtime_config(args)
    pool = _build_lookup_pool(args)
    http = httpx.AsyncClient(
        base_url=args.base_url.rstrip("/") + "/",
        headers={
            "Authorization": f"Bearer {os.environ['ONTCHATBOT_LLM_API_KEY']}",
            "Content-Type": "application/json",
        },
        timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
    )

    async def lookup(keywords: list[str]) -> str:
        return await look_up_async(pool, keywords)

    async def close() -> None:
        await http.aclose()
        await pool.aclose()

    return AgentLoop(
        LightningClient(http, model=args.llm),
        lookup,
        instructions=build_instructions(),
        max_steps=MAX_MODEL_STEPS,
        close=close,
    )


def _build_lookup_pool(args: argparse.Namespace):
    """Load both heavy asset groups concurrently before the server starts."""

    from ..runtime.lookup_pool import AsyncLookupPool
    from ..runtime.onnx_classifier import OnnxClassifierGenerator
    from ..runtime.pipeline import OntologyChatbot
    from ..runtime.sparql import load_ontology

    with ThreadPoolExecutor(
        max_workers=2, thread_name_prefix="runtime-init"
    ) as workers:
        loaders = (
            workers.submit(load_ontology),
            workers.submit(
                OnnxClassifierGenerator.load_assets,
                args.model_dir,
                intra_op_threads=args.onnx_threads,
            ),
        )
        loaded = []
        for loader in loaders:
            try:
                loaded.append(loader.result())
            except BaseException as exc:
                loaded.append(exc)

    failure = next(
        (result for result in loaded if isinstance(result, BaseException)), None
    )
    if failure is not None:
        loaded.clear()
        raise failure
    graph, assets = loaded
    generator = OnnxClassifierGenerator.from_assets(assets, graph=graph)
    return AsyncLookupPool(
        OntologyChatbot(generator, graph=graph),
        workers=args.lookup_workers,
        classification_cache_entries=args.classification_cache_entries,
        sparql_cache_bytes=args.sparql_cache_mib * 1024 * 1024,
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
    _log_cpu_budget(
        onnx_threads=args.onnx_threads, lookup_workers=args.lookup_workers
    )

    # ``log_config=None`` để máy chủ web không dựng cấu hình nhật ký riêng của
    # nó. Mặc định, các dòng của nó đi qua một khuôn khác hẳn và KHÔNG có mốc
    # thời gian, nên nhật ký trộn hai kiểu dòng: dòng của dịch vụ có giờ, dòng
    # của máy chủ web thì không. Bỏ cấu hình đó thì mọi dòng cùng một khuôn.
    uvicorn.run(
        create_app(
            _build_agent(args),
            gate=TurnGate(slots=args.turn_slots, queue_size=args.turn_queue),
            backend_token=backend_token,
        ),
        host=args.host,
        port=args.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
