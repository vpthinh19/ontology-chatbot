"""Chọn truy vấn SPARQL bằng cách phân loại câu hỏi vào một nhãn.

Model đọc câu hỏi và chọn một trong khoảng ba trăm nhãn; mỗi nhãn ứng với đúng một
câu truy vấn dựng sẵn từ danh mục. Câu trả về vì thế luôn đúng cú pháp và luôn trỏ
tới thực thể có thật - hai thứ mà cách sinh chuỗi ký tự phải kiểm lại sau khi sinh.

Nhãn là cặp ``(nhóm câu hỏi, danh sách IRI)``. Khoản và điểm được gộp lên Điều chứa
chúng, nên hỏi tới cấp điểm sẽ nhận dữ liệu của cả Điều; phần trích dẫn trong kết
quả vẫn ghi đúng tới điểm.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pyoxigraph as ox

from .cards import CardLookup
from .generator import QueryGenerationError

MAX_LENGTH = 48


class ClassifierGenerator:
    """Trả câu truy vấn ứng với nhãn mà model chọn cho câu hỏi."""

    def __init__(self, encoder, tokenizer, head, labels, lookup, device):
        self._encoder = encoder
        self._tokenizer = tokenizer
        self._head = head
        self._labels = labels
        self._lookup = lookup
        self._device = device
        self._queries = [self._lookup.query(group, anchors) for group, anchors in labels]

    @classmethod
    def load(
        cls,
        model_dir: Path,
        *,
        graph: ox.Store | None = None,
        device: str = "cpu",
    ) -> ClassifierGenerator:
        """Nạp bộ điều hợp, lớp phân loại và bảng nhãn đã lưu lúc huấn luyện."""
        import torch
        import torch.nn as nn
        from peft import PeftModel
        from transformers import AutoModel, AutoTokenizer

        model_dir = Path(model_dir)
        meta_path = model_dir / "labels.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"không tìm thấy bảng nhãn: {meta_path}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        base = AutoModel.from_pretrained(meta["base_model"])
        encoder = PeftModel.from_pretrained(base, model_dir).eval().to(device)

        head = nn.Linear(base.config.hidden_size, len(meta["labels"]))
        head.load_state_dict(torch.load(model_dir / "head.pt", map_location=device))
        head = head.eval().to(device)

        labels = []
        for key in meta["labels"]:
            parts = key.split("|")
            labels.append((parts[0], tuple(parts[1:])))

        lookup = CardLookup() if graph is None else CardLookup(_cards_for(graph))
        return cls(encoder, tokenizer, head, labels, lookup, device)

    @property
    def labels(self) -> Sequence[tuple[str, tuple[str, ...]]]:
        return self._labels

    def generate_many(self, texts: Sequence[str]) -> list[str]:
        import torch

        questions = [text.strip() for text in texts]
        if any(not question for question in questions):
            raise QueryGenerationError("câu hỏi rỗng")

        chosen: list[int] = []
        with torch.no_grad():
            for start in range(0, len(questions), 64):
                encoded = self._tokenizer(
                    questions[start : start + 64],
                    padding=True,
                    truncation=True,
                    max_length=MAX_LENGTH,
                    return_tensors="pt",
                ).to(self._device)
                hidden = self._encoder(**encoded).last_hidden_state
                mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1e-9)
                chosen += self._head(pooled).argmax(dim=1).tolist()
        return [self._queries[index] for index in chosen]

    def generate(self, text: str) -> str:
        return self.generate_many([text])[0]


def _cards_for(graph: ox.Store):
    from .cards import load_cards

    return load_cards(graph)
