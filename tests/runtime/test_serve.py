from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from ontchatbot.runtime.api import create_app
from ontchatbot.runtime.model import QueryGenerationError
from ontchatbot.runtime.render import NO_INFORMATION_REPLY
from ontchatbot.runtime.sparql import SparqlError


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


@pytest.mark.parametrize(
    "error",
    [
        QueryGenerationError("model generated an empty query"),
        SparqlError("invalid SPARQL"),
    ],
)
def test_http_api_returns_no_information_for_expected_query_failures(
    tmp_path, error
) -> None:
    def reject(_: str) -> str:
        raise error

    chatbot = SimpleNamespace(answer=reject)

    async def exercise_api():
        transport = httpx.ASGITransport(app=create_app(chatbot, webui_dir=tmp_path))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json={"message": "mai có mưa không"})

    response = asyncio.run(exercise_api())
    assert response.status_code == 200
    assert response.json() == {"reply": NO_INFORMATION_REPLY}


def test_http_api_does_not_hide_unexpected_system_errors(tmp_path) -> None:
    def fail(_: str) -> str:
        raise RuntimeError("boom")

    chatbot = SimpleNamespace(answer=fail)

    async def exercise_api():
        transport = httpx.ASGITransport(
            app=create_app(chatbot, webui_dir=tmp_path),
            raise_app_exceptions=False,
        )
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/chat", json={"message": "học phí"})

    response = asyncio.run(exercise_api())
    assert response.status_code == 500
