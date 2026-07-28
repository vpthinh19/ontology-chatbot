from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from ontchatbot.runtime.api import create_app
from ontchatbot.runtime.pipeline import OUT_OF_SCOPE_REPLY, OutOfScopeError


def test_http_api_health_and_chat(tmp_path) -> None:
    chatbot = SimpleNamespace(answer=lambda question: f"đáp án cho: {question}")

    async def exercise_api():
        transport = httpx.ASGITransport(app=create_app(chatbot, webui_dir=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/healthz")
            response = await client.post("/chat", json={"message": "bảo lưu thế nào"})
        return health, response

    health, response = asyncio.run(exercise_api())
    assert health.json() == {"status": "ok"}
    assert response.status_code == 200
    assert response.json() == {"reply": "đáp án cho: bảo lưu thế nào"}


def test_http_api_rejects_empty_message(tmp_path) -> None:
    chatbot = SimpleNamespace(answer=lambda _: "unused")

    async def exercise_api():
        transport = httpx.ASGITransport(app=create_app(chatbot, webui_dir=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json={"message": "  "})

    response = asyncio.run(exercise_api())
    assert response.status_code == 400


def test_http_api_returns_stable_reply_for_out_of_scope_message(tmp_path) -> None:
    def reject(_: str) -> str:
        raise OutOfScopeError(OUT_OF_SCOPE_REPLY)

    chatbot = SimpleNamespace(answer=reject)

    async def exercise_api():
        transport = httpx.ASGITransport(app=create_app(chatbot, webui_dir=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json={"message": "mai có mưa không"})

    response = asyncio.run(exercise_api())
    assert response.status_code == 200
    assert response.json() == {"reply": OUT_OF_SCOPE_REPLY}
