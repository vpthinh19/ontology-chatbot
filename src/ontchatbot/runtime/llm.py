"""Sinh truy vấn bằng LLM có nhắc ví dụ hoặc đã tinh chỉnh.

Cài đặt cùng giao diện với ``CTranslate2Generator``: đưa vào câu hỏi, trả ra một
chuỗi truy vấn. Tầng chạy áp dụng cùng các bước kiểm cho mọi model.

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


class _QueryGeneratorBase:
    """Phần chung của mọi cách sinh truy vấn: chuẩn hóa, gọi model, dọn kết quả.

    Chỉ ``build_prompt`` khác nhau giữa model có nhắc ví dụ và model đã tinh chỉnh.
    """

    def __init__(
        self,
        complete: Callable[[str], str],
        *,
        complete_batch: Callable[[Sequence[str]], Sequence[str]] | None = None,
    ) -> None:
        self._complete = complete
        self._complete_batch = complete_batch

    def build_prompt(self, question: str) -> str:
        raise NotImplementedError

    def generate(self, text: str) -> str:
        question = normalize_model_input(text)
        raw = self._complete(self.build_prompt(question))
        return _clean(raw)

    def generate_many(self, texts: Sequence[str]) -> list[str]:
        """Sinh cho nhiều câu một lượt, giữ nguyên thứ tự đưa vào.

        Dùng cùng các bước chuẩn hóa, dựng prompt và dọn kết quả như ``generate``.
        Nếu không có ``complete_batch``, gọi model cho từng câu.
        """

        prompts = [
            self.build_prompt(normalize_model_input(text)) for text in texts
        ]
        if not prompts:
            return []
        if self._complete_batch is None:
            return [_clean(self._complete(prompt)) for prompt in prompts]
        raw = list(self._complete_batch(prompts))
        if len(raw) != len(prompts):
            raise ValueError(
                f"gom lô trả về {len(raw)} kết quả cho {len(prompts)} câu hỏi"
            )
        return [_clean(text) for text in raw]


class FineTunedQueryGenerator(_QueryGeneratorBase):
    """Sinh truy vấn bằng model ĐÃ tinh chỉnh: câu hỏi trần, không ví dụ nhắc.

    Model đã học thuộc bài thì không cần ai nhắc bài. Đưa ví dụ vào là đưa nó
    một khuôn khác hẳn khuôn nó được dạy - dài gấp mấy chục lần, thiếu lời hệ
    thống - và nó sẽ quay sang bắt chước ví dụ thay vì dùng thứ đã học.

    Phần bọc câu hỏi thành hội thoại nằm ở bên gọi, vì đó là việc của bộ tách
    từ. Ở đây chỉ đảm bảo câu hỏi được chuẩn hoá y như lúc huấn luyện.
    """

    def build_prompt(self, question: str) -> str:
        return question


class LLMQueryGenerator(_QueryGeneratorBase):
    """Sinh truy vấn bằng một LLM CHƯA tinh chỉnh, nhắc kèm ví dụ.

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
        complete_batch: Callable[[Sequence[str]], Sequence[str]] | None = None,
    ) -> None:
        if shots < 1:
            raise ValueError("cần ít nhất một ví dụ nhắc kèm")
        super().__init__(complete, complete_batch=complete_batch)
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
