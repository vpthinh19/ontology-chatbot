"""Validate the released SPARQL dataset against ontology v11."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..settings import DATASET_DIR
from ..research.dataset import load_release, validate_release
from ..runtime.sparql import load_ontology


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DATASET_DIR)
    args = parser.parse_args()
    report = validate_release(load_release(args.path), load_ontology())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
