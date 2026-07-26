from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from ontchatbot.scripts.serve import create_app


def test_http_api_health_and_chat(tmp_path) -> None:
    chatbot = SimpleNamespace(answer=lambda question: f"đáp án cho: {question}")
    client = TestClient(create_app(chatbot, webui_dir=tmp_path))

    assert client.get("/healthz").json() == {"status": "ok"}
    response = client.post("/chat", json={"message": "bảo lưu thế nào"})

    assert response.status_code == 200
    assert response.json() == {"reply": "đáp án cho: bảo lưu thế nào"}


def test_http_api_rejects_empty_message(tmp_path) -> None:
    chatbot = SimpleNamespace(answer=lambda _: "unused")
    client = TestClient(create_app(chatbot, webui_dir=tmp_path))

    response = client.post("/chat", json={"message": "  "})

    assert response.status_code == 400
