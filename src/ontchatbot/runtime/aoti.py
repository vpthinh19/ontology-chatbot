"""Sinh câu truy vấn bằng gói đã biên dịch sẵn.

Cả bộ mã hoá lẫn từng bước giải mã được biên dịch trước thành mã máy và đóng
thành gói, nên lúc phục vụ không cần thư viện huấn luyện: chỉ nạp gói rồi gọi.

Vòng giải mã chiếm gần trọn thời gian một lượt sinh, và trước nay không biên
dịch được vì bộ nhớ đệm khoá-giá trị dài thêm sau mỗi chữ, làm hình dạng phép
tính đổi liên tục. Cấp sẵn bộ đệm cho trọn độ dài tối đa thì hình dạng cố định
và cả vòng biên dịch được.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

from .model import MAX_SOURCE_LENGTH, MAX_TARGET_LENGTH, QueryGenerationError
from .text import normalize_model_input

#: Bộ mã hoá đệm chuỗi vào về bội của tám rồi bớt một, nên mọi đầu vào phải đưa
#: về đúng dạng đó trước khi gọi.
SOURCE_LENGTH_STEP = 8
#: Chuỗi vào ngắn hơn mức này vẫn được đệm lên, vì gói dựng theo một chiều nhỏ nhất.
MIN_SOURCE_LENGTH = 15
#: Hình dạng bộ đệm khoá-giá trị của phần giải mã, cấp một lần cho trọn lượt sinh.
DECODER_LAYERS = 18
DECODER_KV_HEADS = 1
DECODER_HEAD_DIM = 256


def padded_source_length(length: int) -> int:
    """Độ dài chuỗi vào sau khi đệm, luôn có dạng tám nhân một số trừ một."""

    step = SOURCE_LENGTH_STEP * math.ceil((length + 1) / SOURCE_LENGTH_STEP) - 1
    return max(MIN_SOURCE_LENGTH, step)


class AotiGenerator:
    """Sinh một câu truy vấn từ gói đã biên dịch sẵn, mỗi lần một câu."""

    def __init__(self, encoder, decoder, tokenizer, torch) -> None:
        self._encoder = encoder
        self._decoder = decoder
        self._tokenizer = tokenizer
        self._torch = torch
        self._pad = tokenizer.pad_token_id or 0
        self._eos = tokenizer.eos_token_id
        self._start = tokenizer.bos_token_id
        if self._start is None:
            self._start = 2
        # Ô vị trí cấp riêng một lần rồi ghi tại chỗ: cắt lát từ một dãy dài cho
        # ra con trỏ lệch nửa ô ở các bước lẻ, mà mã đã biên dịch giả định con
        # trỏ căn đủ, nên nó phải sao chép lại trước mỗi bước.
        self._position = torch.zeros(1, dtype=torch.long, device="cuda")

    @classmethod
    def load(cls, package_dir: Path, tokenizer_dir: Path) -> AotiGenerator:
        try:
            import torch
            from transformers import AutoTokenizer
        except ImportError as exc:  # pragma: no cover - cần thêm phần suy luận.
            raise RuntimeError("install the inference extra to load a model") from exc

        package_dir = Path(package_dir)
        encoder_path = package_dir / "encoder.pt2"
        decoder_path = package_dir / "decoder.pt2"
        for path in (encoder_path, decoder_path):
            if not path.is_file():
                raise FileNotFoundError(f"AOTInductor package not found: {path}")
        if not torch.cuda.is_available():
            raise RuntimeError("the compiled packages require a CUDA device")
        return cls(
            torch._inductor.aoti_load_package(encoder_path),
            torch._inductor.aoti_load_package(decoder_path),
            AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True),
            torch,
        )

    def generate(self, text: str) -> str:
        return self.generate_many([text])[0]

    def generate_many(self, texts: Sequence[str]) -> list[str]:
        """Sinh cho nhiều câu, mỗi câu độc lập.

        Các câu chạy lần lượt chứ không gộp: gộp buộc phải đệm mọi câu về cùng
        độ dài, và phần đệm làm kết quả của một câu đổi theo những câu đi cùng.
        """

        sources = [normalize_model_input(text) for text in texts]
        if any(not source for source in sources):
            raise ValueError("question is empty")
        return [self._one(source) for source in sources]

    def _one(self, source: str) -> str:
        torch = self._torch
        encoded = self._tokenizer(
            source,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_SOURCE_LENGTH,
        )
        length = padded_source_length(encoded["input_ids"].shape[1])
        pad = lambda tensor, value: torch.nn.functional.pad(  # noqa: E731
            tensor, (0, length - tensor.shape[1]), value=value
        )
        input_ids = pad(encoded["input_ids"], self._pad).cuda()
        attention_mask = pad(encoded["attention_mask"], 0).cuda()

        with torch.inference_mode():
            hidden, cross_keys, cross_values = self._encoder(input_ids, attention_mask)
            self_keys = torch.zeros(
                (DECODER_LAYERS, 1, DECODER_KV_HEADS, MAX_TARGET_LENGTH, DECODER_HEAD_DIM),
                dtype=torch.bfloat16,
                device="cuda",
            )
            self_values = torch.zeros_like(self_keys)
            token = torch.tensor([[self._start]], dtype=torch.long, device="cuda")
            produced: list[int] = []
            for step in range(MAX_TARGET_LENGTH):
                self._position.fill_(step)
                token = self._decoder(
                    token,
                    self._position,
                    hidden,
                    attention_mask,
                    self_keys,
                    self_values,
                    cross_keys,
                    cross_values,
                )[0]
                token_id = int(token.item())
                produced.append(token_id)
                if token_id == self._eos:
                    break

        query = self._tokenizer.decode(produced, skip_special_tokens=True).strip()
        if not query:
            raise QueryGenerationError("model generated an empty query")
        return query
