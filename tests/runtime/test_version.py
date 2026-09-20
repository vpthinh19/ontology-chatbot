from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import ontchatbot

#: Engine tìm kiếm đọc ontology bằng pyoxigraph và xếp hạng dòng chỉ mục bằng bm25s.
SEARCH_LIBRARIES = {"bm25s", "pyoxigraph"}


def _project() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]


def _names(requirements: list[str]) -> set[str]:
    return {item.split("[")[0].split(">=")[0] for item in requirements}


def test_release_version_and_service_dependencies() -> None:
    project = _project()
    assert project["version"] == ontchatbot.__version__ == "4.1.0"
    assert _names(project["optional-dependencies"]["inference"]) == {"httpx", "pyshacl", "starlette", "uvicorn"}


def test_the_deployed_dependencies_carry_the_search_engine() -> None:
    project = _project()
    deployed = _names(project["dependencies"]) | _names(project["optional-dependencies"]["inference"])

    assert SEARCH_LIBRARIES <= deployed


def test_package_version_matches_installed_release() -> None:
    assert ontchatbot.__version__ == version("ontchatbot")
