import json
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_dockerfile_is_cpu_only_and_uses_three_slim_stages() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    lowered = text.lower()
    assert text.count("FROM python:3.12-slim-bookworm") == 3
    for stage in ("builder", "model-fetcher", "runtime"):
        assert f" AS {stage}" in text
    assert "nvidia" not in lowered
    assert "cuda" not in lowered
    assert "ontchatbot_device" not in lowered


def test_runtime_copies_only_production_resources() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY resources/ ./resources/" not in text
    assert "COPY resources/ontology/ ./resources/ontology/" in text
    assert " /app/resources /app/resources" not in text
    assert " /app/resources/ontology /app/resources/ontology" in text


def test_runtime_keeps_the_service_contract() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime = text.split(" AS runtime", maxsplit=1)[1]
    assert "COPY --from=model-fetcher" in runtime
    assert " /app/model /app/model" in runtime
    for setting in (
        "ONTCHATBOT_ONNX_THREADS=1",
        "ONTCHATBOT_LOOKUP_WORKERS=8",
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
    assert json.loads(cmd) == [
        "serve_sparql",
        "--model-dir",
        "/app/model",
        "--host",
        "0.0.0.0",
    ]


def test_cpu_verifier_replaces_gpu_only_scripts() -> None:
    scripts = ROOT / ".github" / "scripts"
    verifier = scripts / "verify-cpu-runtime.sh"
    assert verifier.is_file()
    assert not (scripts / "verify-cuda-runtime.sh").exists()
    assert not (scripts / "prepare-runner-disk.sh").exists()

    text = verifier.read_text(encoding="utf-8")
    for forbidden in ("dataset", "reports", "provenance", "end-to-end", "cases"):
        assert f"/app/resources/{forbidden}" in text
    for required in ("ontology.ttl", "catalogue.jsonl", "answer_inventory.json"):
        assert f"/app/resources/ontology/{required}" in text
    for marker in (
        "command -v uv",
        "onnxruntime-gpu",
        "nvidia-",
        "CPUExecutionProvider",
        "generator.generate",
    ):
        assert marker in text


def test_release_workflow_measures_and_verifies_the_cpu_image() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "prepare-runner-disk.sh" not in text
    assert "verify-cuda-runtime.sh" not in text
    assert "ONTCHATBOT_DEVICE" not in text
    assert "verify-cpu-runtime.sh" in text
    assert "docker image inspect --format '{{.Size}}'" in text
    assert "docker history --no-trunc" in text
    assert "cuda image" not in text.lower()
