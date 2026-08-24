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


def test_cpu_verifier_replaces_gpu_only_scripts() -> None:
    scripts = ROOT / ".github" / "scripts"
    assert (scripts / "verify-cpu-runtime.sh").is_file()
    assert not (scripts / "verify-cuda-runtime.sh").exists()
    assert not (scripts / "prepare-runner-disk.sh").exists()
