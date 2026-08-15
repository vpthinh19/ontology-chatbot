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
    staticfiles = ModuleType("fastapi.staticfiles")
    staticfiles.StaticFiles = SimpleNamespace
    monkeypatch.setitem(sys.modules, "fastapi", fastapi)
    monkeypatch.setitem(sys.modules, "fastapi.staticfiles", staticfiles)

    app = create_app(SimpleNamespace(answer=lambda _: "unused"), webui_dir=tmp_path)

    assert app.version == ontchatbot.__version__


class _FakeFastAPI:
    def __init__(self, *, title: str, version: str) -> None:
        self.title = title
        self.version = version

    def get(self, _path: str):
        return lambda endpoint: endpoint

    def post(self, _path: str):
        return lambda endpoint: endpoint

    def mount(self, *_args, **_kwargs) -> None:
        pass
