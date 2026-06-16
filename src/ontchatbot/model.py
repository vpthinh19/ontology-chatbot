"""Model: ViT5 seq2seq sinh CÂY JSON từ text (DESIGN.md §3).

**Khung cho phiên train sau.** ViT5 chưa train (cần GPU) nên :meth:`sinh_cay` báo lỗi
rõ ràng thay vì trả rác. Hợp đồng I/O cố định để `pipeline`/`tree` không phải đổi khi
model về:

    sinh_cay(text: str) -> dict   # {"act": ..., "entities": [...]}  (xem tree.parse)

Khi train xong (phiên sau): nạp tokenizer + ONNX/transformers seq2seq cục bộ (hoặc
``snapshot_download`` từ HF repo người dùng), generate, ``json.loads`` ra dict trên.
Nguyên tắc: model làm TOÀN BỘ việc hiểu câu (trích xuất, dựng quan hệ, đoán act); không
có luật xử-lý-câu ở pipeline (§9).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from .config import FINETUNED_MODEL_NAME

log = logging.getLogger(__name__)


class ModelChuaSanSang(RuntimeError):
    """ViT5 chưa train/chưa nạp được — pipeline không chạy text→cây được."""


class TreeModel:
    """Giao diện sinh cây. Phiên này chỉ là khung (chưa có weight)."""

    def __init__(self, model_name: str = FINETUNED_MODEL_NAME) -> None:
        self.model_name = model_name
        self._ready = False          # phiên train sau: nạp tokenizer + session ở đây

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "TreeModel":
        return cls()

    @staticmethod
    def available() -> bool:
        """True khi đã có weight để chạy. Hiện tại: False (chưa train)."""
        return False

    def sinh_cay(self, text: str) -> dict:
        """text → dict cây JSON. Chưa train → báo lỗi rõ ràng."""
        raise ModelChuaSanSang(
            "ViT5 chưa train — pipeline text→cây chưa chạy được. "
            "Phiên này test bằng cây JSON vàng nạp thẳng vào ontology.traverse "
            "(xem docs/redesign/PROGRESS.md, Phase train sau)."
        )
