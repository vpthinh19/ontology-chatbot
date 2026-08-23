from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT = Path(".github/scripts/prepare-runner-disk.sh")
CLEANUP_PATHS = (
    "usr/local/lib/android",
    "usr/share/dotnet",
    "opt/ghc",
    "usr/local/.ghcup",
    "opt/hostedtoolcache/CodeQL",
)


def _executable(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\nset -eu\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


def _run(tmp_path: Path, *, available_gib: int) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    cleanup_root = tmp_path / "runner"
    calls = tmp_path / "calls"
    fake_bin.mkdir()
    for relative in CLEANUP_PATHS:
        (cleanup_root / relative).mkdir(parents=True)

    _executable(fake_bin / "sudo", 'printf "sudo %s\\n" "$*" >> "$CALLS"')
    _executable(fake_bin / "docker", 'printf "docker %s\\n" "$*" >> "$CALLS"')
    _executable(
        fake_bin / "df",
        f'''if [ "${{1:-}}" = "--output=avail" ]; then
    printf "Avail\\n%d\\n" $(({available_gib} * 1024 * 1024))
else
    printf "Filesystem Size Used Avail Use%% Mounted on\\n"
fi''',
    )
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "CALLS": str(calls),
        "RUNNER_CLEANUP_ROOT": str(cleanup_root),
    }
    return subprocess.run(
        ["sh", str(SCRIPT)],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cleanup_removes_only_declared_runner_tools_and_prunes_docker(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path, available_gib=20)

    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "calls").read_text(encoding="utf-8").splitlines()
    expected_removals = [
        f"sudo rm -rf --one-file-system -- {tmp_path / 'runner' / relative}"
        for relative in CLEANUP_PATHS
    ]
    assert calls == [*expected_removals, "docker system prune --all --force"]


def test_cleanup_fails_early_when_the_runner_still_has_too_little_space(
    tmp_path: Path,
) -> None:
    result = _run(tmp_path, available_gib=10)

    assert result.returncode != 0
    assert "at least 18 GiB" in result.stderr
