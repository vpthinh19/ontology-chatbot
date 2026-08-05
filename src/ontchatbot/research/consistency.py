"""Read-only consistency checks for canonical data and derived artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Literal, Mapping

from ..runtime.sparql import load_ontology
from ..settings import (
    ANSWER_INVENTORY_PATH,
    DATASET_DIR,
    ONTOLOGY_PATH,
    PROJECT_ROOT,
)
from ..catalogue import load_catalogue
from .catalogue_validation import validate_catalogue
from .dataset import REQUIRED_SPLITS, load_release
from .inventory import build_answer_inventory
from .reporting import (
    build_dataset_report,
    build_manifest,
    build_procedure_dataset_report,
    sha256_file,
)

CANONICAL_INPUT_NAMES = (
    "ontology.ttl",
    "catalogue.jsonl",
    "coverage.json",
    "train.jsonl",
    "val.jsonl",
    "test.jsonl",
)


class ConsistencyError(ValueError):
    """Canonical derived artifacts do not match their source inputs."""


@dataclass(frozen=True)
class ArtifactPaths:
    inventory: Path
    manifest: Path
    dataset_report: Path
    procedure_report: Path
    provenance: Path


@dataclass(frozen=True)
class ConsistencySnapshot:
    inventory: dict[str, object]
    catalogue_validation: dict[str, object]
    dataset_report: dict[str, object]
    manifest: dict[str, object]
    procedure_report: dict[str, object]
    provenance: dict[str, object]


def canonical_artifact_paths() -> ArtifactPaths:
    reports_dir = PROJECT_ROOT / "reports"
    return ArtifactPaths(
        inventory=ANSWER_INVENTORY_PATH,
        manifest=DATASET_DIR / "manifest.json",
        dataset_report=reports_dir / "dataset.json",
        procedure_report=reports_dir / "procedure-dataset.json",
        provenance=reports_dir / "provenance.json",
    )


def build_input_fingerprint(
    *,
    dataset_dir: Path = DATASET_DIR,
    ontology_path: Path = ONTOLOGY_PATH,
) -> dict[str, str]:
    paths = {
        "ontology.ttl": Path(ontology_path),
        "catalogue.jsonl": Path(dataset_dir) / "catalogue.jsonl",
        "coverage.json": Path(dataset_dir) / "coverage.json",
        **{
            f"{split}.jsonl": Path(dataset_dir) / f"{split}.jsonl"
            for split in REQUIRED_SPLITS
        },
    }
    return {name: sha256_file(paths[name]) for name in CANONICAL_INPUT_NAMES}


def classify_provenance(
    baseline_inputs: Mapping[str, str],
    current_inputs: Mapping[str, str],
) -> Literal["current", "stale", "unverified"]:
    expected = set(CANONICAL_INPUT_NAMES)
    if set(baseline_inputs) != expected or set(current_inputs) != expected:
        return "unverified"
    if any(
        not isinstance(value, str) or len(value) != 64
        for value in (*baseline_inputs.values(), *current_inputs.values())
    ):
        return "unverified"
    return "current" if dict(baseline_inputs) == dict(current_inputs) else "stale"


def build_consistency_snapshot(
    *,
    dataset_dir: Path = DATASET_DIR,
    ontology_path: Path = ONTOLOGY_PATH,
    paths: ArtifactPaths | None = None,
) -> ConsistencySnapshot:
    artifact_paths = paths or canonical_artifact_paths()
    graph = load_ontology(ontology_path)
    inventory = build_answer_inventory(graph)
    catalogue = load_catalogue(Path(dataset_dir) / "catalogue.jsonl")
    catalogue_validation = validate_catalogue(graph, inventory, catalogue)
    release = load_release(dataset_dir)
    dataset_report = build_dataset_report(
        release,
        graph,
        dataset_dir=dataset_dir,
        ontology_path=ontology_path,
    )
    manifest = build_manifest(
        dataset_report,
        manifest_path=artifact_paths.manifest,
        ontology_path=ontology_path,
    )
    procedure_report = build_procedure_dataset_report(
        release,
        dataset_dir=dataset_dir,
    )
    provenance = _build_provenance(
        artifact_paths.provenance,
        build_input_fingerprint(
            dataset_dir=dataset_dir,
            ontology_path=ontology_path,
        ),
    )
    return ConsistencySnapshot(
        inventory=inventory,
        catalogue_validation=catalogue_validation,
        dataset_report=dataset_report,
        manifest=manifest,
        procedure_report=procedure_report,
        provenance=provenance,
    )


def compare_committed_artifacts(
    snapshot: ConsistencySnapshot,
    *,
    paths: ArtifactPaths | None = None,
) -> list[dict[str, object]]:
    artifact_paths = paths or canonical_artifact_paths()
    expected = {
        "inventory": snapshot.inventory,
        "manifest": snapshot.manifest,
        "dataset_report": snapshot.dataset_report,
        "procedure_report": snapshot.procedure_report,
        "provenance": snapshot.provenance,
    }
    mismatches: list[dict[str, object]] = []
    for field in fields(artifact_paths):
        stage = field.name
        path = getattr(artifact_paths, stage)
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            committed = None
        if committed != expected[stage]:
            mismatches.append(
                {
                    "stage": stage,
                    "path": str(path),
                    "action": "regenerate derived artifacts",
                }
            )
    return mismatches


def require_consistent(mismatches: list[dict[str, object]]) -> None:
    if not mismatches:
        return
    details = ", ".join(
        f"{item['stage']} ({item['path']})" for item in mismatches
    )
    raise ConsistencyError(f"derived artifact mismatch: {details}")


def _build_provenance(path: Path, current_inputs: dict[str, str]) -> dict[str, object]:
    try:
        existing = json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        existing = {}
    baseline_inputs = existing.get("baseline_inputs", {})
    if not isinstance(baseline_inputs, dict):
        baseline_inputs = {}
    status = classify_provenance(baseline_inputs, current_inputs)
    return {
        "schema_version": 1,
        "baseline_release": existing.get("baseline_release", "v0.4.1"),
        "provenance_basis": existing.get(
            "provenance_basis", "adopted_from_release_v0.4.1"
        ),
        "baseline_inputs": baseline_inputs,
        "current_inputs": current_inputs,
        "model_metrics": {"status": status},
        "deployment_metrics": {"status": status},
    }
