"""Mechanical staging and deterministic assembly for dataset curation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ..settings import RESOURCES
from .catalogue import QuerySpec
from .dataset import REQUIRED_FIELDS, REQUIRED_SPLITS

DOMAIN_DIRECTORIES = {
    "procedure": "procedure",
    "tuition": "tuition-academic-rule",
    "academic-rule": "tuition-academic-rule",
    "certificate": "certificate-form-document",
    "form": "certificate-form-document",
    "out-of-domain": "out-of-domain",
}
DOMAIN_ORDER = (
    "procedure",
    "tuition-academic-rule",
    "certificate-form-document",
    "out-of-domain",
)
CHECKLIST_FILENAME = "rejection_checklist.json"
_CHECKLIST_SOURCE = RESOURCES / "cases" / CHECKLIST_FILENAME


class CurationError(ValueError):
    """Staged rows or their rejection checklist cannot form a release."""


def bootstrap_staging(
    release: Mapping[str, list[dict[str, str]]],
    catalogue: Mapping[str, QuerySpec],
    staging_dir: Path,
) -> None:
    """Route existing release rows into the four human-curated staging shards."""

    staging_dir = Path(staging_dir)
    _require_splits(release)
    routed = {
        domain: {split: [] for split in REQUIRED_SPLITS} for domain in DOMAIN_ORDER
    }
    for split in REQUIRED_SPLITS:
        for row in release[split]:
            _validate_row(row, context=f"{split} staging row")
            query_id = row["query_id"]
            spec = catalogue.get(query_id)
            if spec is None:
                raise CurationError(f"unknown query_id: {query_id}")
            routed[DOMAIN_DIRECTORIES[spec.domain]][split].append(dict(row))

    staging_dir.mkdir(parents=True, exist_ok=True)
    for domain in DOMAIN_ORDER:
        domain_dir = staging_dir / domain
        domain_dir.mkdir(exist_ok=True)
        for split in REQUIRED_SPLITS:
            _write_jsonl(domain_dir / f"{split}.jsonl", routed[domain][split])
    (staging_dir / "reviews").mkdir(exist_ok=True)
    (staging_dir / CHECKLIST_FILENAME).write_text(
        _CHECKLIST_SOURCE.read_text(encoding="utf-8"), encoding="utf-8"
    )


def assemble_staging(
    staging_dir: Path,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[str]]]:
    """Assign stable release IDs and remap the staging rejection checklist."""

    staging_dir = Path(staging_dir)
    release = {split: [] for split in REQUIRED_SPLITS}
    remapped_ids: dict[str, str] = {}
    out_of_domain_ids: set[str] = set()
    sequence = 1

    for split in REQUIRED_SPLITS:
        for domain in DOMAIN_ORDER:
            rows = _load_jsonl(staging_dir / domain / f"{split}.jsonl")
            for row in sorted(rows, key=lambda item: item["id"]):
                temporary_id = row["id"]
                if temporary_id in remapped_ids:
                    raise CurationError(f"duplicate temporary id: {temporary_id}")
                release_id = f"question-{sequence:06d}"
                remapped_ids[temporary_id] = release_id
                if domain == "out-of-domain":
                    out_of_domain_ids.add(temporary_id)
                release[split].append({**row, "id": release_id})
                sequence += 1

    checklist = _load_checklist(staging_dir / CHECKLIST_FILENAME)
    remapped_checklist: dict[str, list[str]] = {}
    for rejection_class, temporary_ids in checklist.items():
        remapped: list[str] = []
        for temporary_id in temporary_ids:
            if temporary_id not in out_of_domain_ids:
                raise CurationError(
                    "checklist id is not an out-of-domain row: " f"{temporary_id}"
                )
            remapped.append(remapped_ids[temporary_id])
        remapped_checklist[rejection_class] = remapped
    return release, remapped_checklist


def _require_splits(release: Mapping[str, object]) -> None:
    if set(release) != set(REQUIRED_SPLITS):
        raise CurationError(f"release must contain exactly {list(REQUIRED_SPLITS)}")


def _validate_row(row: object, *, context: str) -> None:
    if not isinstance(row, dict) or set(row) != REQUIRED_FIELDS:
        raise CurationError(f"{context}: fields must be exactly {sorted(REQUIRED_FIELDS)}")
    if not all(isinstance(value, str) and value for value in row.values()):
        raise CurationError(f"{context}: every field must be non-empty text")


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    payload = "".join(
        f"{json.dumps(row, ensure_ascii=False, separators=(',', ':'))}\n" for row in rows
    )
    path.write_text(payload, encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, str]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise CurationError(f"missing staging split: {path}") from exc

    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CurationError(f"{path}:{line_number}: invalid JSON") from exc
        _validate_row(row, context=f"{path}:{line_number}")
        rows.append(row)
    return rows


def _load_checklist(path: Path) -> dict[str, list[str]]:
    try:
        checklist = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CurationError(f"missing staging checklist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CurationError(f"invalid staging checklist: {path}") from exc
    if not isinstance(checklist, dict) or not all(
        isinstance(rejection_class, str)
        and isinstance(ids, list)
        and all(isinstance(record_id, str) for record_id in ids)
        for rejection_class, ids in checklist.items()
    ):
        raise CurationError("staging checklist must map classes to temporary ID lists")
    return checklist
