"""Sinh truy vấn bằng LLM có nhắc ví dụ, thay cho seq2seq đã tinh chỉnh.

Cài đặt cùng giao diện với ``CTranslate2Generator``: đưa vào câu hỏi, trả ra một
chuỗi truy vấn. Bốn cửa kiểm ở tầng chạy không đổi, nên LLM bịa cũng bị chặn y
như model cũ.

Ví dụ nhắc kèm được lấy từ chính tập huấn luyện, chọn theo độ giống chữ. Không
dùng vector nhúng: câu hỏi ở đây ngắn và hay viết tắt, viết không dấu, nên so
theo cụm ký tự bắt được những biến dạng đó mà không cần thêm model.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .text import normalize_model_input

MARKER = "không có thông tin"

_INSTRUCTION = """Bạn chuyển câu hỏi học vụ tiếng Việt thành một truy vấn SPARQL trên ontology của Trường Đại học Nha Trang.

Quy tắc:
- Chỉ in ra truy vấn SPARQL, không giải thích, không rào đầu rào đuôi.
- Bắt chước ĐÚNG khuôn các ví dụ bên dưới: cùng tên biến, cùng thuộc tính, cùng cách viết.
- Chỉ dùng thực thể và thuộc tính đã xuất hiện trong ví dụ. Không được bịa tên mới.
- Nếu câu hỏi nằm ngoài phạm vi học vụ, hoặc thiếu thông tin để xác định một đáp án duy nhất, hãy in đúng một dòng: {marker}"""


def _shingles(text: str) -> Counter:
    """Đếm cụm 3 ký tự của câu đã hạ thường và bỏ dấu câu."""

    cleaned = re.sub(r"[^0-9a-zà-ỹ ]+", " ", text.casefold())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    padded = f"  {cleaned}  "
    return Counter(padded[i : i + 3] for i in range(len(padded) - 2))


def _similarity(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0
    shared = sum((left & right).values())
    return shared / (len(left) + len(right) - shared)


@dataclass(frozen=True)
class Example:
    question: str
    target: str
    _shingles: Counter

    @classmethod
    def build(cls, question: str, target: str) -> Example:
        return cls(question, target, _shingles(question))


def load_examples(path: Path) -> tuple[Example, ...]:
    """Đọc kho ví dụ từ một tệp jsonl của dataset."""

    examples = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        examples.append(Example.build(row["input"], row["target"]))
    if not examples:
        raise ValueError(f"kho ví dụ rỗng: {path}")
    return tuple(examples)


class LLMQueryGenerator:
    """Sinh truy vấn bằng một LLM bất kỳ, gọi qua ``complete``.

    ``complete`` nhận prompt đã dựng sẵn và trả về văn bản model sinh ra. Tách
    như vậy để đổi model không phải sửa gì ở đây - chạy local hay gọi dịch vụ
    đều cắm vào cùng một chỗ.
    """

    def __init__(
        self,
        complete: Callable[[str], str],
        examples: Sequence[Example],
        *,
        shots: int = 12,
    ) -> None:
        if shots < 1:
            raise ValueError("cần ít nhất một ví dụ nhắc kèm")
        self._complete = complete
        self._examples = tuple(examples)
        self._shots = shots

    def nearest(self, question: str) -> tuple[Example, ...]:
        wanted = _shingles(question)
        ranked = sorted(
            self._examples,
            key=lambda example: _similarity(wanted, example._shingles),
            reverse=True,
        )
        return tuple(ranked[: self._shots])

    def build_prompt(self, question: str) -> str:
        # Ví dụ giống nhất đặt SÁT câu hỏi: phần cuối prompt là phần model chú ý
        # nhất, nên xếp tăng dần theo độ giống.
        chosen = tuple(reversed(self.nearest(question)))
        blocks = "\n\n".join(
            f"Câu hỏi: {example.question}\nTruy vấn: {example.target}"
            for example in chosen
        )
        instruction = _INSTRUCTION.format(marker=MARKER)
        return f"{instruction}\n\n{blocks}\n\nCâu hỏi: {question}\nTruy vấn:"

    def generate(self, text: str) -> str:
        question = normalize_model_input(text)
        raw = self._complete(self.build_prompt(question))
        return _clean(raw)


def _clean(raw: str) -> str:
    """Gỡ rào code và phần thừa sau truy vấn."""

    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = text.split("```", 1)[0]
    text = text.strip()
    if text.casefold().startswith(MARKER):
        return MARKER
    # Lời giải thích thừa, nếu có, nằm sau một dòng trống. ĐỪNG cắt ở dấu đóng
    # ngoặc cuối: ``ORDER BY`` và ``LIMIT`` nằm SAU nó, cắt là truy vấn cụt và
    # không còn khớp danh mục nữa.
    text = text.split("\n\n", 1)[0]
    return " ".join(text.split())


def truncate_examples(
    examples: Iterable[Example], keep: int | None
) -> tuple[Example, ...]:
    """Cắt bớt kho ví dụ, dùng khi muốn đo ảnh hưởng của cỡ kho."""

    chosen = tuple(examples)
    return chosen if keep is None else chosen[:keep]
