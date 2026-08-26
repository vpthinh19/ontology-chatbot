"""Chat with the same lightweight agent loop used by the HTTP service."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ..runtime.agent import DEFAULT_BASE_URL
from .serve import _build_agent


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_MODEL_DIR"),
        help="thư mục bộ phân loại: bộ điều hợp, lớp phân loại và bảng nhãn",
    )
    parser.add_argument(
        "--llm",
        default=os.environ.get("ONTCHATBOT_LLM_MODEL", ""),
        help="tên mô hình ngôn ngữ lớn trên máy chủ API",
    )
    parser.add_argument("--base-url", default=None, help=f"mặc định {DEFAULT_BASE_URL}")
    parser.add_argument("--hoi", default=None, help="hỏi một câu rồi thoát")
    return parser.parse_args(argv)


def _runtime_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        model_dir=args.model_dir,
        llm=args.llm,
        base_url=args.base_url
        or os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_BASE_URL),
        onnx_threads=1,
        lookup_workers=4,
        classification_cache_entries=4096,
        sparql_cache_mib=64,
    )


def main() -> None:
    args = _parse_args()
    if not args.llm:
        raise SystemExit(
            "chưa chỉ định mô hình ngôn ngữ lớn: dùng --llm hoặc đặt "
            "ONTCHATBOT_LLM_MODEL"
        )
    if not args.model_dir:
        raise SystemExit("cần --model-dir")

    agent = _build_agent(_runtime_args(args))

    async def ask(question: str) -> None:
        wrote = False
        print()
        async for event in agent.stream([{"role": "user", "content": question}]):
            if event.kind == "lookup_started":
                print(f"    [công cụ] tra {list(event.keywords)!r}", flush=True)
            elif event.kind == "text_delta":
                wrote = True
                print(event.content, end="", flush=True)
            elif event.kind == "completed" and not wrote:
                print(event.content, end="", flush=True)
        print("\n")

    with asyncio.Runner() as runner:
        if args.hoi:
            runner.run(ask(args.hoi))
            return

        print("Gõ câu hỏi rồi Enter. Dòng trống để thoát.\n")
        while True:
            try:
                question = input("hỏi> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not question:
                return
            runner.run(ask(question))


if __name__ == "__main__":
    main()
