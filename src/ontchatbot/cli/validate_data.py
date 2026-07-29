"""Validate a SPARQL dataset against the canonical ontology."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..settings import DATASET_DIR
from ..research.catalogue import load_catalogue
from ..research.coverage import (
    assess_coverage,
    load_coverage_requirements,
    require_complete_coverage,
)
from ..research.dataset import load_release, validate_release
from ..runtime.sparql import load_ontology


def _load_rejection_checklist(dataset_dir: Path) -> dict[str, list[str]]:
    path = Path(dataset_dir).parent.parent / "cases" / "rejection_checklist.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DATASET_DIR)
    args = parser.parse_args()
    release = load_release(args.path)
    catalogue = load_catalogue(args.path / "catalogue.jsonl")
    report = validate_release(
        release,
        load_ontology(),
        catalogue,
        require_complete_catalogue=False,
    )
    coverage = assess_coverage(
        release,
        catalogue,
        load_coverage_requirements(args.path / "coverage.json", catalogue),
        _load_rejection_checklist(args.path),
    )
    require_complete_coverage(coverage)
    print(
        json.dumps(
            {"release": report, "coverage": coverage},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
