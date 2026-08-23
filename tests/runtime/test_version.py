from __future__ import annotations

import sys
from importlib.metadata import version
from types import ModuleType, SimpleNamespace

import ontchatbot
from ontchatbot.runtime.api import create_app


def test_package_version_matches_installed_release() -> None:
    assert ontchatbot.__version__ == version("ontchatbot")


def test_http_api_reports_the_production_release(monkeypatch, tmp_path) -> None:
    fastapi = ModuleType("fastapi")
    fastapi.FastAPI = _FakeFastAPI
    fastapi.HTTPException = RuntimeError
    # Phải giả lập ĐỦ mọi module con mà ``create_app`` nạp. Thiếu một cái thì phép
    # kiểm chỉ chạy được khi một phép kiểm khác đã nạp bản thật trước đó, tức là nó
    # xanh lúc chạy cả thư mục và đỏ lúc chạy riêng tệp này.
    middleware = ModuleType("fastapi.middleware")
    cors = ModuleType("fastapi.middleware.cors")
    cors.CORSMiddleware = SimpleNamespace
    responses = ModuleType("fastapi.responses")
    responses.StreamingResponse = SimpleNamespace
    monkeypatch.setitem(sys.modules, "fastapi", fastapi)
    monkeypatch.setitem(sys.modules, "fastapi.middleware", middleware)
    monkeypatch.setitem(sys.modules, "fastapi.middleware.cors", cors)
    monkeypatch.setitem(sys.modules, "fastapi.responses", responses)

    app = create_app(SimpleNamespace(answer=lambda _: "unused"))

    assert app.version == ontchatbot.__version__


class _FakeFastAPI:
    def __init__(self, *, title: str, version: str) -> None:
        self.title = title
        self.version = version

    def get(self, _path: str):
        return lambda endpoint: endpoint

    def post(self, _path: str):
        return lambda endpoint: endpoint

    def add_middleware(self, *_args, **_kwargs) -> None:
        pass
