"""Model: BARTpho-syllable seq2seq sinh CÂY JSON từ text (DESIGN.md §3).

Inference qua **CTranslate2** (int8, CPU — ràng buộc deploy) + **sentencepiece TRỰC TIẾP**
(KHÔNG cần transformers/torch — deploy chỉ core deps + fastapi). BARTpho là mBART (encoder-decoder),
đi theo pattern :class:`ctranslate2.Translator` token→token (KHÔNG dùng HF ``generate``):

    src = ["<s>"] + sp.EncodeAsPieces(text) + ["</s>"]   # khớp ĐÚNG transformers (đã verify parity)
    out = translator.translate_batch([src])[0].hypotheses[0]
    json_str = sp.DecodePieces([t for t in out if t not in SPECIAL])

rồi ``json.loads`` ra ``{"act", "entities": [...]}`` (xem :func:`tree.parse`). Model làm TOÀN BỘ
việc hiểu câu (trích xuất, dựng quan hệ, đoán act) — pipeline không có luật xử-lý-câu (§9).

⚠️ Vì sao sentencepiece chứ KHÔNG transformers.AutoTokenizer: đường deploy phải gọn (core +
fastapi), tránh kéo cả hệ sinh thái transformers. Người dùng đã test (`dev/inf_test.py`) và parity
``["<s>"] + EncodeAsPieces + ["</s>"]`` == ``AutoTokenizer.convert_ids_to_tokens(encode(...))``
đã được kiểm (khớp tuyệt đối) nên KHÔNG lệch so với lúc train/eval.

⚠️ :meth:`to_tree` nhận text **ĐÃ qua ``preprocess.clean``** (pipeline clean trước khi gọi — đồng bộ
với train/eval); KHÔNG clean lại ở đây. JSON model sinh hỏng → trả cây ``vague`` (khoan dung như
production, không ném lỗi giữa request). Model CT2 nạp từ ``config.CT2_MODEL_DIR`` (convert bằng
``scripts.convert_ct2``); thiếu cục bộ → ``snapshot_download`` từ HF repo người dùng.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from .config import CT2_MODEL_DIR, CT2_QUANTIZATION, FINETUNED_MODEL_NAME, MAX_SOURCE_LENGTH, MAX_TARGET_LENGTH
from .tree import from_model_json

log = logging.getLogger(__name__)

_BEAM_SIZE = 4            # khớp evaluate.py/convert_ct2 (giữ parity train↔eval↔serve); tăng=chính xác hơn, chậm hơn
_VAGUE_TREE = {"act": "vague", "entities": []}
_BOS, _EOS = "<s>", "</s>"
_SPECIAL = {"<s>", "</s>", "<pad>", "<unk>", "<mask>"}     # lọc khỏi output trước khi DecodePieces


class ModelNotReady(RuntimeError):
    """Không tìm được model CT2 (chưa convert + không tải được từ HF) → pipeline không chạy text→cây."""


class TreeModel:
    """Sinh cây JSON từ text qua CTranslate2 + sentencepiece. Nạp lười (lần gọi đầu) + cache singleton."""

    def __init__(self, model_dir: Path | str = CT2_MODEL_DIR) -> None:
        self._dir = Path(model_dir)
        self._translator = None      # ctranslate2.Translator (nạp lười)
        self._sp = None              # sentencepiece.SentencePieceProcessor (nạp lười)

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "TreeModel":
        return cls()

    @staticmethod
    def available() -> bool:
        """True khi đã có model CT2 cục bộ (``model.bin``). Không xét đường tải HF (mạng)."""
        return (CT2_MODEL_DIR / "model.bin").exists()

    def _load(self) -> None:
        """Nạp Translator + sentencepiece (lười). Cục bộ trước; thiếu → tải HF; vẫn không có → ModelNotReady."""
        if self._translator is not None:
            return
        import ctranslate2
        import sentencepiece as spm

        path = self._dir
        if not (path / "model.bin").exists():
            log.warning("[model] không thấy CT2 cục bộ ở %s — thử snapshot_download %s",
                        path, FINETUNED_MODEL_NAME)
            try:
                from huggingface_hub import snapshot_download
                path = Path(snapshot_download(FINETUNED_MODEL_NAME))
            except Exception as e:                       # noqa: BLE001 — gói mọi lỗi tải về 1 lỗi rõ
                raise ModelNotReady(
                    f"Chưa có model CT2 cục bộ ({self._dir}) và không tải được HF "
                    f"{FINETUNED_MODEL_NAME!r}: {e}. Chạy scripts.convert_ct2 trước.") from e
        self._translator = ctranslate2.Translator(str(path), device="cpu",
                                                   compute_type=CT2_QUANTIZATION)
        self._sp = spm.SentencePieceProcessor()
        self._sp.Load(str(Path(path) / "sentencepiece.bpe.model"))
        log.info("[model] CT2 + sentencepiece sẵn sàng: %s (beam=%d)", path, _BEAM_SIZE)

    def to_tree(self, text: str) -> dict:
        """text (đã clean) → dict cây JSON. JSON hỏng → cây ``vague`` (khoan dung, không ném lỗi)."""
        self._load()
        pieces = self._sp.EncodeAsPieces(text)[: MAX_SOURCE_LENGTH - 2]   # chừa chỗ <s>…</s>
        src = [_BOS] + pieces + [_EOS]                                    # khớp transformers (parity verified)
        hyp = self._translator.translate_batch(
            [src], beam_size=_BEAM_SIZE, max_decoding_length=MAX_TARGET_LENGTH)
        out = [t for t in hyp[0].hypotheses[0] if t not in _SPECIAL]
        json_str = self._sp.DecodePieces(out)
        try:
            return from_model_json(json_str)               # bỏ pad + items→entities → dict cây chuẩn
        except (json.JSONDecodeError, TypeError):
            log.warning("[model] JSON hỏng từ model: %r", json_str[:200])
            return dict(_VAGUE_TREE)
