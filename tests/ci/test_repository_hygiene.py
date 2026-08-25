from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]


def test_public_repository_excludes_internal_development_material() -> None:
    tracked = set(
        subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )
    internal = sorted(
        path
        for path in tracked
        if path == "docs/deploy-cloud-run.md"
        or path.startswith("docs/superpowers/")
    )
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert internal == []
    assert "## vận hành dịch vụ" not in readme
    assert "deploy-cloud-run" not in readme
    assert "superpowers" not in readme
