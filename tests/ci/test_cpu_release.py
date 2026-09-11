import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_dockerfile_is_cpu_only_and_uses_two_slim_stages() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    lowered = text.lower()
    assert text.count("FROM python:3.12-slim-bookworm") == 2
    for stage in ("builder", "runtime"):
        assert f" AS {stage}" in text
    assert "model-fetcher" not in text
    assert "nvidia" not in lowered
    assert "cuda" not in lowered


def test_runtime_copies_only_production_resources() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY resources/ ./resources/" not in text
    assert "COPY resources/ontology/ ./resources/ontology/" in text
    assert " /app/resources /app/resources" not in text
    assert " /app/resources/ontology /app/resources/ontology" in text
    assert "bake_cards" not in text


def test_runtime_keeps_the_service_contract() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = text.split(" AS runtime", maxsplit=1)[1]
    assert "/app/model" not in runtime
    for setting in (
        "ONTCHATBOT_ONTOLOGY_PATH=/app/resources/ontology/ontology.ttl",
        "ONTCHATBOT_SEARCH_WORKERS=4",
        "ONTCHATBOT_TURN_SLOTS=4",
        "ONTCHATBOT_TURN_QUEUE=8",
    ):
        assert setting in runtime
    assert "USER ontchatbot" in runtime
    cmd = next(
        line.removeprefix("CMD ")
        for line in runtime.splitlines()
        if line.startswith("CMD ")
    )
    assert json.loads(cmd) == ["serve_sparql", "--host", "0.0.0.0"]


def test_cpu_verifier_checks_the_search_runtime() -> None:
    scripts = ROOT / ".github" / "scripts"
    verifier = scripts / "verify-cpu-runtime.sh"
    assert verifier.is_file()
    assert not (scripts / "verify-cuda-runtime.sh").exists()
    assert not (scripts / "prepare-runner-disk.sh").exists()

    text = verifier.read_text(encoding="utf-8")
    for forbidden in ("dataset", "reports", "provenance", "end-to-end", "cases"):
        assert f"/app/resources/{forbidden}" in text
    assert "/app/resources/ontology/ontology.ttl" in text
    for marker in ("command -v uv", "nvidia-", "onnxruntime", "SearchEngine", "engine.search"):
        assert marker in text


def test_release_workflow_measures_and_verifies_the_cpu_image() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "prepare-runner-disk.sh" not in text
    assert "verify-cuda-runtime.sh" not in text
    assert "ONTCHATBOT_DEVICE" not in text
    assert "HF_MODEL_REPO" not in text
    assert "verify-cpu-runtime.sh" in text
    assert "docker image inspect --format '{{.Size}}'" in text
    assert "docker history --no-trunc" in text
    assert "cuda image" not in text.lower()
