"""pipeline: điều phối qua cây vàng (answer_tree) + chốt model chưa sẵn sàng."""

from __future__ import annotations

import pytest

from ontchatbot.model import ModelNotReady
from ontchatbot.pipeline import Pipeline


def test_answer_tree_reaches_right_nodes():
    res = Pipeline.get().answer_tree({"act": "query", "entities": [
        {"label": "bảo lưu", "type": "individual", "children": [
            {"label": "điều kiện", "type": "object", "children": []}]}]})
    iris = {e["iri"] for e in res["entities"]}
    assert iris == {"DieuKienBaoLuuCaNhan", "DieuKienBaoLuuQuocTe",
                    "DieuKienBaoLuuVuTrang", "DieuKienBaoLuuYTe"}
    assert res["reply"]


def test_answer_tree_greeting():
    res = Pipeline.get().answer_tree({"act": "greeting", "entities": []})
    assert res["entities"] == []
    assert "Xin chào" in res["reply"]


def test_answer_needs_trained_model():
    # ViT5 chưa train → luồng text→cây phải báo lỗi rõ ràng, không trả rác.
    with pytest.raises(ModelNotReady):
        Pipeline.get().answer("xin chào")
