"""Chọn truy vấn bằng đồ thị ONNX, không cần thư viện huấn luyện.

Đây là đường dùng khi phục vụ. Nó cần đúng ba thứ: bộ chạy ONNX, thư viện tách từ,
và mảng số - cộng lại vài trăm megabyte thay vì vài gigabyte của thư viện huấn luyện
kèm các thư viện tính toán của card đồ hoạ.

Đồ thị đã gộp sẵn bộ mã hoá, phép gộp trung bình và lớp phân loại, nên ở đây chỉ còn
tách từ, chạy một lượt, rồi tra nhãn ra truy vấn.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import numpy as np
import rdflib

from .cards import CardLookup
from .generator import QueryGenerationError

MAX_LENGTH = 48


class OnnxClassifierGenerator:
    """Trả câu truy vấn ứng với nhãn mà đồ thị ONNX chọn cho câu hỏi."""

    def __init__(self, session, tokenizer, labels, lookup, pad_id: int):
        self._session = session
        self._tokenizer = tokenizer
        self._labels = labels
        self._lookup = lookup
        self._pad_id = pad_id
        self._queries = [self._lookup.query(group, anchors) for group, anchors in labels]

    @classmethod
    def load(
        cls,
        model_dir: Path,
        *,
        graph: rdflib.Graph | None = None,
        device: str = "cuda",
    ) -> OnnxClassifierGenerator:
        """Nạp đồ thị, bộ tách từ và bảng nhãn từ thư mục đã xuất."""
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = Path(model_dir)
        graph_path = model_dir / "classifier.onnx"
        if not graph_path.exists():
            raise FileNotFoundError(f"không tìm thấy đồ thị ONNX: {graph_path}")

        if device == "cuda":
            # CUDA và cuDNN nằm trong image runtime chính thức của NVIDIA. Chuỗi
            # rỗng yêu cầu ORT dùng đường dẫn loader hệ thống của image thay vì
            # tìm các wheel CUDA đóng kèm trong site-packages.
            ort.preload_dlls(directory="")
            providers = ["CUDAExecutionProvider"]
        else:
            providers = ["CPUExecutionProvider"]
        session = ort.InferenceSession(str(graph_path), providers=providers)
        if device == "cuda":
            # Cấm Python API tạo lại cả session bằng CPU nếu provider lỗi. ORT
            # vẫn được phép giao vài node điều phối/shape nhẹ cho CPU mặc định;
            # graph này không khởi tạo được nếu cấm tuyệt đối các node như vậy.
            session.disable_fallback()
        if device == "cuda" and "CUDAExecutionProvider" not in session.get_providers():
            raise RuntimeError(
                "không thể kích hoạt CUDAExecutionProvider; "
                "kiểm tra GPU passthrough và CUDA/cuDNN runtime trong image"
            )

        tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        tokenizer.enable_truncation(max_length=MAX_LENGTH)
        pad_id = tokenizer.token_to_id("<pad>")
        if pad_id is None:
            pad_id = 1
        tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")

        meta = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))
        labels = []
        for key in meta["labels"]:
            parts = key.split("|")
            labels.append((parts[0], tuple(parts[1:])))

        lookup = CardLookup() if graph is None else CardLookup(_cards_for(graph))
        return cls(session, tokenizer, labels, lookup, pad_id)

    @property
    def labels(self) -> Sequence[tuple[str, tuple[str, ...]]]:
        return self._labels

    @property
    def providers(self) -> list[str]:
        return self._session.get_providers()

    def generate_many(self, texts: Sequence[str]) -> list[str]:
        questions = [text.strip() for text in texts]
        if any(not question for question in questions):
            raise QueryGenerationError("câu hỏi rỗng")

        encoded = self._tokenizer.encode_batch(questions)
        input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
        logits = self._session.run(
            ["logits"],
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )[0]
        return [self._queries[index] for index in logits.argmax(axis=1)]

    def generate(self, text: str) -> str:
        return self.generate_many([text])[0]


def _cards_for(graph: rdflib.Graph):
    from .cards import build_cards

    return build_cards(graph)
