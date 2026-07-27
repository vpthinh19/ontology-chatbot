"""Create the Stage G audit from frozen experiment reports."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..research.stage_g import write_stage_g_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts/sparql_official_v2"))
    parser.add_argument("--learning-artifacts", type=Path, default=Path("artifacts/sparql_stage_g_v2"))
    args = parser.parse_args()
    audit = write_stage_g_outputs(args.artifacts, args.learning_artifacts)
    print(f"Stage G: {audit['status']}")


if __name__ == "__main__":
    main()
