"""Model: BARTpho-syllable seq2seq sinh CÂY JSON từ text (DESIGN.md §3).

**Khung cho phiên train sau.** Model chưa train (cần GPU) nên :meth:`to_tree` báo lỗi
rõ ràng thay vì trả rác. Hợp đồng I/O cố định để `pipeline`/`tree` không phải đổi khi
model về:

    to_tree(text: str) -> dict   # {"act": ..., "entities": [...]}  (xem tree.parse)

Khi train xong (phiên sau): nạp model **CTranslate2** cục bộ (`config.CT2_MODEL_DIR`) hoặc
``snapshot_download`` từ HF repo người dùng. BARTpho là mBART (encoder-decoder) → inference
theo pattern Translator (KHÔNG dùng HF ``generate``):

    src = tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
    out = translator.translate_batch([src])[0].hypotheses[0]
    json_str = tokenizer.decode(tokenizer.convert_tokens_to_ids(out), skip_special_tokens=True)

rồi ``json.loads(json_str)`` ra dict trên. Nguyên tắc: model làm TOÀN BỘ việc hiểu câu
(trích xuất, dựng quan hệ, đoán act); không có luật xử-lý-câu ở pipeline (§9).
"""

from __future__ import annotations

import logging
from functools import lru_cache

from .config import FINETUNED_MODEL_NAME

log = logging.getLogger(__name__)


class ModelNotReady(RuntimeError):
    """BARTpho chưa train/chưa nạp được — pipeline không chạy text→cây được."""


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

    def to_tree(self, text: str) -> dict:
        """text → dict cây JSON. Chưa train → báo lỗi rõ ràng."""
        raise ModelNotReady(
            "BARTpho chưa train — pipeline text→cây chưa chạy được. "
            "Phiên này test bằng cây JSON vàng nạp thẳng vào ontology.traverse "
            "(xem docs/redesign/PROGRESS.md, Phase train sau)."
        )
