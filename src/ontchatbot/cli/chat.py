"""Hỏi trợ lý từ dòng lệnh, bằng cùng vòng hỏi đáp của dịch vụ HTTP."""

from __future__ import annotations

import argparse
import asyncio
import os
from dataclasses import replace
from pathlib import Path

from ..runtime.service import Config, Service
from ..settings import DEFAULT_LLM_BASE_URL, ONTOLOGY_PATH


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ontology", type=Path,
                        default=os.environ.get("ONTCHATBOT_ONTOLOGY_PATH", str(ONTOLOGY_PATH)),
                        help="tệp TriG của ontology")
    parser.add_argument("--llm", default=os.environ.get("ONTCHATBOT_LLM_MODEL", ""),
                        help="tên mô hình ngôn ngữ lớn trên máy chủ API")
    parser.add_argument("--base-url", default=None, help=f"mặc định {DEFAULT_LLM_BASE_URL}")
    parser.add_argument("--hoi", default=None, help="hỏi một câu rồi thoát")
    return parser.parse_args(argv)


def _config(args: argparse.Namespace) -> Config:
    """Chỉ trợ lý: đọc tệp ontology trên đĩa, không trang quản trị, không Cloud Storage, không lịch sử chat."""

    base_url = args.base_url or os.environ.get("ONTCHATBOT_LLM_BASE_URL", DEFAULT_LLM_BASE_URL)
    config = Config.from_env(ontology=Path(args.ontology), llm_model=args.llm, llm_base_url=base_url,
                             search_workers=2, top_k=5)
    return replace(config, admin_token="", gcs_uri="", chat_log=False)


def _open_agent(config: Config) -> tuple:
    service = Service(config).start()
    return service.agent, service.aclose


async def _ask(agent, question: str) -> None:
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


def main() -> None:
    args = _parse_args()
    agent, close = _open_agent(_config(args))
    with asyncio.Runner() as runner:
        try:
            if args.hoi:
                runner.run(_ask(agent, args.hoi))
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
                runner.run(_ask(agent, question))
        finally:
            runner.run(close())


if __name__ == "__main__":
    main()
