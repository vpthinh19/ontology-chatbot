import json
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_dockerfile_uses_two_slim_stages() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert text.count("FROM python:3.12-slim-bookworm") == 2
    for stage in ("builder", "runtime"):
        assert f" AS {stage}" in text


def test_runtime_copies_only_the_ontology_resources() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY resources/ ./resources/" not in text
    assert "COPY resources/ontology/ ./resources/ontology/" in text
    assert " /app/resources/ontology /app/resources/ontology" in text


def test_runtime_keeps_the_service_contract() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = text.split(" AS runtime", maxsplit=1)[1]
    for setting in (
        "ONTCHATBOT_ONTOLOGY_PATH=/app/resources/ontology/ontology.trig",
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
    assert json.loads(cmd) == ["serve_chatbot", "--host", "0.0.0.0"]


def test_image_verifier_checks_the_search_runtime() -> None:
    text = (ROOT / ".github" / "scripts" / "verify-cpu-runtime.sh").read_text(encoding="utf-8")
    assert "/app/resources/ontology/ontology.trig" in text
    for marker in ("command -v uv", "TriGFileSource", "engine.search"):
        assert marker in text


def test_release_workflow_measures_and_verifies_the_image() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "verify-cpu-runtime.sh" in text
    assert "docker image inspect --format '{{.Size}}'" in text
    assert "docker history --no-trunc" in text
