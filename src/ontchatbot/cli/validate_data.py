"""Validate a SPARQL dataset against the canonical ontology."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..research.consistency import (
    build_consistency_snapshot,
    compare_committed_artifacts,
    require_consistent,
)
from ..research.coverage import require_complete_coverage
from ..settings import DATASET_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DATASET_DIR)
    args = parser.parse_args()
    snapshot = build_consistency_snapshot(dataset_dir=args.path)
    coverage = snapshot.dataset_report["coverage"]
    require_complete_coverage(coverage)

    is_canonical = args.path.resolve() == DATASET_DIR.resolve()
    if is_canonical:
        mismatches = compare_committed_artifacts(snapshot)
        require_consistent(mismatches)
        artifacts = {
            "checked": True,
            "mismatches": mismatches,
        }
    else:
        artifacts = {
            "checked": False,
            "reason": "noncanonical dataset directory",
            "mismatches": [],
        }

    inventory_entries = snapshot.inventory["entries"]
    assert isinstance(inventory_entries, list)
    print(
        json.dumps(
            {
                "inventory": {
                    "entries": len(inventory_entries),
                    "supported_entries": sum(
                        entry.get("status") == "supported"
                        for entry in inventory_entries
                        if isinstance(entry, dict)
                    ),
                    "excluded_entries": sum(
                        entry.get("status") == "excluded"
                        for entry in inventory_entries
                        if isinstance(entry, dict)
                    ),
                },
                "catalogue": snapshot.catalogue_validation,
                "release": snapshot.dataset_report["validation"],
                "coverage": coverage,
                "artifacts": artifacts,
                "provenance": snapshot.provenance,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
