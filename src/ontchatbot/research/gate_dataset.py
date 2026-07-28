"""Load and validate the binary ontology-domain gate dataset."""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..runtime.text import normalize_model_input

GATE_LABELS = ("in_scope", "out_of_scope")
GATE_SPLITS = ("train", "val", "test")
_FIELDS = frozenset(("input", "label"))
_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)


def _duplicate_key(text: str) -> str:
    return _NON_WORD.sub("", normalize_model_input(text).casefold())


def load_gate_release(path: Path) -> dict[str, list[dict[str, str]]]:
    """Load the three required JSON Lines splits from *path*."""

    release: dict[str, list[dict[str, str]]] = {}
    for split in GATE_SPLITS:
        split_path = Path(path) / f"{split}.jsonl"
        if not split_path.is_file():
            raise FileNotFoundError(f"gate dataset split not found: {split_path}")
        rows = []
        for line_number, line in enumerate(
            split_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{split_path}:{line_number}: row must be an object")
            rows.append(row)
        release[split] = rows
    return release


def validate_gate_release(
    release: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    """Return a machine-readable report for the gate dataset contract."""

    errors: list[dict[str, object]] = []
    split_reports: dict[str, dict[str, int]] = {}
    seen_inputs: dict[str, tuple[str, int]] = {}

    for split in GATE_SPLITS:
        rows = release.get(split, [])
        counts = {label: 0 for label in GATE_LABELS}
        for index, row in enumerate(rows, start=1):
            location = {"split": split, "row": index}
            if not isinstance(row, dict) or frozenset(row) != _FIELDS:
                errors.append({"code": "invalid_fields", **location})
                continue

            text = row.get("input")
            label = row.get("label")
            if not isinstance(text, str) or not text.strip():
                errors.append({"code": "empty_input", **location})
            else:
                normalized = _duplicate_key(text)
                previous = seen_inputs.get(normalized)
                if previous is not None:
                    errors.append(
                        {
                            "code": "duplicate_input",
                            **location,
                            "first_split": previous[0],
                            "first_row": previous[1],
                        }
                    )
                else:
                    seen_inputs[normalized] = (split, index)

            if label not in GATE_LABELS:
                errors.append({"code": "invalid_label", **location})
            else:
                counts[label] += 1

        split_reports[split] = {
            "records": len(rows),
            **counts,
        }
        if counts["in_scope"] != counts["out_of_scope"]:
            errors.append(
                {
                    "code": "class_imbalance",
                    "split": split,
                    **counts,
                }
            )

    return {
        "valid": not errors,
        "records": sum(report["records"] for report in split_reports.values()),
        "splits": split_reports,
        "errors": errors,
    }
