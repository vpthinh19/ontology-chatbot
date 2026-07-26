"""Validate the released SPARQL dataset against ontology v11."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..config import DATASET_PATH
from ..dataset import load_dataset, validate_dataset
from ..query_engine import load_ontology


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DATASET_PATH)
    args = parser.parse_args()
    report = validate_dataset(load_dataset(args.path), load_ontology())
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
