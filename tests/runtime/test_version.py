from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import ontchatbot


def test_cpu_release_version_and_inference_dependencies() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["version"] == "3.2.0"
    inference = project["project"]["optional-dependencies"]["inference"]
    names = {item.split("[")[0].split(">=")[0] for item in inference}
    assert names == {"httpx", "starlette", "uvicorn", "onnxruntime", "tokenizers"}
    assert "onnxruntime-gpu" not in names
    assert not {name for name in names if name.startswith("nvidia-")}
    assert ontchatbot.__version__ == "3.2.0"


def test_package_version_matches_installed_release() -> None:
    assert ontchatbot.__version__ == version("ontchatbot")


def test_lazy_public_api_remains_visible_to_introspection() -> None:
    assert set(ontchatbot.__all__) <= set(dir(ontchatbot))
