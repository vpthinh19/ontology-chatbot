"""Trò chuyện với trợ lý học vụ ở dòng lệnh.

    python -m ontchatbot.cli.chat --model-dir <thư mục bộ phân loại đã huấn luyện>
    python -m ontchatbot.cli.chat --model-dir <...> --hoi "bảo lưu cần làm gì"

Trợ lý là một mô hình ngôn ngữ lớn gọi qua mạng; nó dùng công cụ tra cứu chạy
tại chỗ để lấy dữ kiện. Lệnh này cho thấy cả hai phía: câu trả lời cuối cùng, và
những từ khoá mà mô hình đã gửi cho công cụ.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from ..runtime.agent import DEFAULT_BASE_URL, build_agent
from ..runtime.onnx_classifier import OnnxClassifierGenerator
from ..runtime.pipeline import OntologyChatbot


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=os.environ.get("ONTCHATBOT_MODEL_DIR"),
        help="thư mục bộ phân loại: bộ điều hợp, lớp phân loại và bảng nhãn",
    )
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument(
        "--llm",
        default=os.environ.get("ONTCHATBOT_LLM_MODEL", ""),
        help="tên mô hình ngôn ngữ lớn trên máy chủ API",
    )
    parser.add_argument("--base-url", default=None, help=f"mặc định {DEFAULT_BASE_URL}")
    parser.add_argument("--hoi", default=None, help="hỏi một câu rồi thoát")
    return parser.parse_args(argv)


class _Trace:
    """Ghi lại từ khoá mà mô hình gửi cho công cụ.

    Đây là chỗ hỏng khó thấy nhất của kiến trúc này: mô hình gửi cả câu hỏi dài
    thay vì từ khoá, công cụ tra trượt, và câu trả lời cuối vẫn trôi chảy nên
    không ai biết. In từ khoá ra là cách rẻ nhất để nhìn thấy điều đó.
    """

    def __init__(self, chatbot: OntologyChatbot) -> None:
        self._chatbot = chatbot

    def answer(self, question: str) -> str:
        reply = self._chatbot.answer(question)
        print(f"    [công cụ] tra {question!r} → {len(reply)} ký tự", flush=True)
        return reply


def main() -> None:
    args = _parse_args()
    if not args.llm:
        raise SystemExit(
            "chưa chỉ định mô hình ngôn ngữ lớn: dùng --llm hoặc đặt "
            "ONTCHATBOT_LLM_MODEL"
        )

    if not args.model_dir:
        raise SystemExit("cần --model-dir")
    generator = OnnxClassifierGenerator.load(args.model_dir, device=args.device)
    agent = build_agent(
        _Trace(OntologyChatbot(generator)),
        model=args.llm,
        base_url=args.base_url,
    )

    from agents import Runner

    async def ask(question: str) -> None:
        result = await Runner.run(agent, question)
        print(f"\n{result.final_output}\n")

    if args.hoi:
        asyncio.run(ask(args.hoi))
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
        asyncio.run(ask(question))


if __name__ == "__main__":
    main()
