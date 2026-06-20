"""pipeline: điều phối qua cây vàng (answer_tree) + chốt model chưa sẵn sàng."""

from __future__ import annotations

import pytest

from ontchatbot.model import ModelNotReady, TreeModel
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


def test_answer_raises_without_model(monkeypatch, tmp_path):
    # Không có model CT2 (cục bộ + không tải được HF) → luồng text→cây báo lỗi rõ, không trả rác.
    # Hermetic: TreeModel trỏ thư mục rỗng + chặn snapshot_download (không gọi mạng trong test).
    import huggingface_hub
    monkeypatch.setattr(huggingface_hub, "snapshot_download",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("offline (test)")))
    pipe = Pipeline(model=TreeModel(model_dir=tmp_path))
    with pytest.raises(ModelNotReady):
        pipe.answer("xin chào")
