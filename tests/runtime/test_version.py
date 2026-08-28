from __future__ import annotations

import tomllib
from importlib.metadata import version
from pathlib import Path

import ontchatbot

#: Libraries the offline tooling walks the graph with. Creating an rdflib graph
#: pulls in a SPARQL parser that builds its whole grammar at import time, and
#: that cost falls on every cold start of the service.
OFFLINE_GRAPH_LIBRARIES = {"oxrdflib", "pyparsing", "rdflib"}


def _project() -> dict:
    return tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]


def _names(requirements: list[str]) -> set[str]:
    return {item.split("[")[0].split(">=")[0] for item in requirements}


def test_cpu_release_version_and_inference_dependencies() -> None:
    project = _project()
    assert project["version"] == "3.2.1"
    inference = project["optional-dependencies"]["inference"]
    names = _names(inference)
    assert names == {"httpx", "starlette", "uvicorn", "onnxruntime", "tokenizers"}
    assert "onnxruntime-gpu" not in names
    assert not {name for name in names if name.startswith("nvidia-")}
    assert ontchatbot.__version__ == "3.2.1"


def test_the_deployed_extra_leaves_the_offline_graph_libraries_behind() -> None:
    """The container image must carry nothing that only the offline tools use.

    The serving path queries the Oxigraph store directly, so these libraries are
    dead weight in the image. Keeping them out is also what stops an import from
    creeping back onto the serving path without anyone noticing.
    """

    project = _project()
    deployed = _names(project["dependencies"]) | _names(
        project["optional-dependencies"]["inference"]
    )

    assert not deployed & OFFLINE_GRAPH_LIBRARIES
    assert OFFLINE_GRAPH_LIBRARIES <= _names(
        project["optional-dependencies"]["research"]
    )


def test_package_version_matches_installed_release() -> None:
    assert ontchatbot.__version__ == version("ontchatbot")


def test_lazy_public_api_remains_visible_to_introspection() -> None:
    assert set(ontchatbot.__all__) <= set(dir(ontchatbot))
