from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import ontchatbot

#: Thư viện chỉ công cụ ngoại tuyến cũ dùng: huấn luyện, xuất model, chấm và vẽ.
#: Chúng nặng hàng trăm megabyte và không được lọt vào ảnh phục vụ.
OFFLINE_ONLY_LIBRARIES = {
    "matplotlib", "onnx", "onnxruntime", "peft", "scikit-learn", "tokenizers", "torch", "transformers",
}
#: Đường phục vụ đọc ontology bằng rdflib, tách từ ghép bằng underthesea và xếp hạng
#: dòng chỉ mục bằng bm25s.
SEARCH_LIBRARIES = {"bm25s", "rdflib", "underthesea"}


def _project() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]


def _names(requirements: list[str]) -> set[str]:
    return {item.split("[")[0].split(">=")[0] for item in requirements}


def test_release_version_and_inference_dependencies() -> None:
    project = _project()
    assert project["version"] == "3.2.1"
    names = _names(project["optional-dependencies"]["inference"])
    assert names == {"httpx", "starlette", "uvicorn"}
    assert not {name for name in names if name.startswith("nvidia-")}
    assert ontchatbot.__version__ == "3.2.1"


def test_the_deployed_dependencies_carry_the_search_engine_and_nothing_offline() -> None:
    """Ảnh phục vụ mang đủ engine tìm kiếm và không mang thư viện của công cụ ngoại tuyến."""

    project = _project()
    deployed = _names(project["dependencies"]) | _names(project["optional-dependencies"]["inference"])

    assert SEARCH_LIBRARIES <= deployed
    assert not deployed & OFFLINE_ONLY_LIBRARIES


def test_package_version_matches_installed_release() -> None:
    assert ontchatbot.__version__ == version("ontchatbot")


def test_lazy_public_api_remains_visible_to_introspection() -> None:
    assert set(ontchatbot.__all__) <= set(dir(ontchatbot))
