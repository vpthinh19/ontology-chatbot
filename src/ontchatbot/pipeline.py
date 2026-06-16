"""Pipeline: điều phối các pha, một chiều phụ thuộc.

    preprocess → model (text→cây) → tree.parse → ontology.traverse → render

Không chứa logic nghiệp vụ; chỉ nối dây. :meth:`answer` chạy đồng bộ (script/test),
:meth:`aanswer` đẩy sang worker thread cho FastAPI. Response giữ ``{"reply","entities"}``
để server/web UI không phải đổi.

Lưu ý phiên này: ViT5 chưa train nên :meth:`answer` (cần model) sẽ báo lỗi; test/eval dùng
:meth:`answer_cay` nạp thẳng cây JSON vàng (không qua model).
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from .model import TreeModel
from .ontology import KetQua, Ontology
from .preprocess import clean
from .render import render_reply
from .tree import Cay, parse

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, ontology: Ontology | None = None, model: TreeModel | None = None) -> None:
        self.ontology = ontology or Ontology.get()
        self._model = model

    @classmethod
    @lru_cache(maxsize=1)
    def get(cls) -> "Pipeline":
        return cls()

    @property
    def model(self) -> TreeModel:
        if self._model is None:
            self._model = TreeModel.get()
        return self._model

    def answer(self, text: str) -> dict:
        """Luồng thật: text → model sinh cây → duyệt → render. Cần ViT5 (chưa train)."""
        raw = self.model.sinh_cay(clean(text))
        return self._run(parse(raw))

    async def aanswer(self, text: str) -> dict:
        return await asyncio.to_thread(self.answer, text)

    def answer_cay(self, cay_or_raw) -> dict:
        """Entry không cần model (test/eval): nhận :class:`Cay` hoặc dict cây JSON vàng."""
        cay = cay_or_raw if isinstance(cay_or_raw, Cay) else parse(cay_or_raw)
        return self._run(cay)

    def _run(self, cay: Cay) -> dict:
        kq = self.ontology.traverse(cay)
        reply = render_reply(cay, kq)
        log.info("[pipeline] act=%s nodes=%d values=%d misses=%s",
                 cay.act, len(kq.nodes), len(kq.values), kq.misses)
        return {"reply": reply, "entities": _entities(kq)}


def _entities(kq: KetQua) -> list[dict]:
    """Tập node kết quả phẳng cho UI debug (đã khử trùng trong traverse)."""
    return [{"iri": n.iri, "label": n.label, "class": n.cls} for n in kq.nodes]
