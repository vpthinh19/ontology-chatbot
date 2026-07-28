"""Validate the ontology-domain gate dataset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..research.gate_dataset import load_gate_release, validate_gate_release
from ..settings import GATE_DIR


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=GATE_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    report = validate_gate_release(load_gate_release(args.dataset_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["valid"]:
        raise SystemExit(1)
