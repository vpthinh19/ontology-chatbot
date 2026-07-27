"""Create the deterministic family-level Stage E release candidate."""

from __future__ import annotations

import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..runtime.sparql import load_ontology
from ..runtime.text import NORMALIZER_VERSION
from ..settings import PROJECT_ROOT
from .audit import _duplicate_report, _target_terms
from .dataset import REQUIRED_FIELDS, REQUIRED_SPLITS, load_dataset, validate_release

DATASET_DIR = PROJECT_ROOT / "resources/datasets/sparql_v2"
SOURCE_PATH = DATASET_DIR / "coverage_draft.jsonl"
MANIFEST_PATH = DATASET_DIR / "manifest.json"
REVIEW_DIR = PROJECT_ROOT / "reports/dataset_review_v2"
AUDIT_PATH = REVIEW_DIR / "stage_e_audit.json"
CANDIDATE_MANIFEST_PATH = REVIEW_DIR / "stage_e_manifest.json"
ONTOLOGY_PATH = PROJECT_ROOT / "resources/ontology/ontology_v12.ttl"

SPLIT_SEED = 42
SPLIT_ALGORITHM = "family_target_stratified_v1"
FAMILY_QUOTAS = {
    "direct": {"train": 79, "val": 17, "test": 15},
    "graph_hop": {"train": 55, "val": 12, "test": 12},
    "multi_column": {"train": 20, "val": 4, "test": 5},
    "aggregate": {"train": 8, "val": 1, "test": 2},
    "aggregate_filter": {"train": 2, "val": 1, "test": 1},
}
COMPOSITIONAL_HOLDOUT_FAMILIES = {
    "val": {
        "cap-061-f03",
        "cov-tuition-extension-form",
        "cov-student-affairs-contact",
        "cov-count-forms",
        "count-tuition-bands-k66",
    },
    "test": {
        "cov-grade-improvement-outcome",
        "cov-major-change-handling-office",
        "cov-undergraduate-office-contact",
        "cov-count-list-procedures",
        "count-tuition-bands-k63",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _family_groups(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    families: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        families[row["family_id"]].append(row)
    for family, values in families.items():
        if len(values) != 4:
            raise ValueError(f"Stage E expects four records in family {family}")
        if len({row["target"] for row in values}) != 1:
            raise ValueError(f"family has multiple targets: {family}")
        if len({row["query_shape"] for row in values}) != 1:
            raise ValueError(f"family has multiple query shapes: {family}")
    return dict(families)


def split_families(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """Split whole families while keeping evaluation targets independent."""

    families = _family_groups(rows)
    targets_by_shape: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for family, values in families.items():
        row = values[0]
        targets_by_shape[row["query_shape"]][row["target"]].append(family)
    if set(targets_by_shape) != set(FAMILY_QUOTAS):
        raise ValueError(f"unexpected query shapes: {sorted(targets_by_shape)}")

    rng = random.Random(SPLIT_SEED)
    assignments = {
        family: split
        for split, family_ids in COMPOSITIONAL_HOLDOUT_FAMILIES.items()
        for family in family_ids
    }
    if not set(assignments) <= set(families):
        raise ValueError("compositional holdout references an unknown family")
    for split, family_ids in COMPOSITIONAL_HOLDOUT_FAMILIES.items():
        shapes = {families[family][0]["query_shape"] for family in family_ids}
        if shapes != set(FAMILY_QUOTAS):
            raise ValueError(f"{split} compositional holdout must cover every query shape")
        if any(
            sum(
                values[0]["target"] == families[family][0]["target"]
                for values in families.values()
            )
            != 1
            for family in family_ids
        ):
            raise ValueError("compositional holdouts must have targets absent from other families")

    for shape in sorted(targets_by_shape):
        target_groups = targets_by_shape[shape]
        eligible_targets = sorted(
            target
            for target, family_ids in target_groups.items()
            if len(family_ids) >= 2 and not any(family in assignments for family in family_ids)
        )
        rng.shuffle(eligible_targets)
        val_quota = FAMILY_QUOTAS[shape]["val"] - sum(
            families[family][0]["query_shape"] == shape
            for family in COMPOSITIONAL_HOLDOUT_FAMILIES["val"]
        )
        test_quota = FAMILY_QUOTAS[shape]["test"] - sum(
            families[family][0]["query_shape"] == shape
            for family in COMPOSITIONAL_HOLDOUT_FAMILIES["test"]
        )
        val_targets = set(eligible_targets[:val_quota])

        test_candidates = [target for target in eligible_targets if target not in val_targets]
        rng.shuffle(test_candidates)
        test_targets = set(test_candidates[:test_quota])
        if len(test_targets) < test_quota:
            overlap_candidates = [
                target
                for target in eligible_targets
                if target in val_targets and len(target_groups[target]) >= 3
            ]
            rng.shuffle(overlap_candidates)
            test_targets.update(overlap_candidates[: test_quota - len(test_targets)])
        if len(val_targets) != val_quota or len(test_targets) != test_quota:
            raise ValueError(f"cannot satisfy evaluation target quotas for {shape}")

        for target in sorted(target_groups):
            family_ids = sorted(
                family for family in target_groups[target] if family not in assignments
            )
            rng.shuffle(family_ids)
            if target in val_targets:
                assignments[family_ids.pop()] = "val"
            if target in test_targets:
                assignments[family_ids.pop()] = "test"
            for family in family_ids:
                assignments[family] = "train"

    if set(assignments) != set(families):
        raise ValueError("not every family received exactly one split")
    release = {split: [] for split in REQUIRED_SPLITS}
    for row in rows:
        release[assignments[row["family_id"]]].append(row)
    return release


def build_audit(
    source: list[dict[str, str]],
    release: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    source_by_id = {row["id"]: row for row in source}
    output_by_id = {
        row["id"]: row for split in REQUIRED_SPLITS for row in release[split]
    }
    records_preserved = source_by_id == output_by_id
    family_shapes = {
        row["family_id"]: row["query_shape"]
        for split in REQUIRED_SPLITS
        for row in release[split]
    }
    family_counts = {
        split: dict(
            sorted(
                Counter(
                    family_shapes[family]
                    for family in {row["family_id"] for row in release[split]}
                ).items()
            )
        )
        for split in REQUIRED_SPLITS
    }
    target_sets = {
        split: {row["target"] for row in release[split]} for split in REQUIRED_SPLITS
    }
    train_terms = set().union(*(_target_terms(row["target"]) for row in release["train"]))
    missing_terms = {
        split: sorted(
            set().union(*(_target_terms(row["target"]) for row in release[split])) - train_terms
        )
        for split in ("val", "test")
    }
    targets_missing_from_train = {
        split: sorted(target_sets[split] - target_sets["train"])
        for split in ("val", "test")
    }
    indexed = [
        dict(row, _split=split) for split in REQUIRED_SPLITS for row in release[split]
    ]
    duplicates = _duplicate_report(indexed, 0.84)
    cross_split_near = [pair for pair in duplicates["near"]["pairs"] if pair["cross_split"]]
    shape_quota_ok = all(
        family_counts[split].get(shape, 0) == count
        for shape, quotas in FAMILY_QUOTAS.items()
        for split, count in quotas.items()
    )
    missing_target_shapes = {
        split: sorted(
            {
                row["query_shape"]
                for row in release[split]
                if row["target"] in targets_missing_from_train[split]
            }
        )
        for split in ("val", "test")
    }
    blockers = (
        not records_preserved,
        not shape_quota_ok,
        bool(target_sets["val"] & target_sets["test"]),
        duplicates["exact"]["cross_split_pairs"] > 0,
        bool(cross_split_near),
        any(missing_terms.values()),
        any(len(targets_missing_from_train[split]) != 5 for split in ("val", "test")),
        any(
            missing_target_shapes[split] != sorted(FAMILY_QUOTAS)
            for split in ("val", "test")
        ),
    )
    return {
        "stage": "E",
        "status": "family_split_complete" if not any(blockers) else "review_required",
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "source_sha256": _sha256(SOURCE_PATH),
        "algorithm": SPLIT_ALGORITHM,
        "seed": SPLIT_SEED,
        "records_preserved": records_preserved,
        "family_query_shape_counts": family_counts,
        "family_query_shape_quotas": FAMILY_QUOTAS,
        "shape_quotas_satisfied": shape_quota_ok,
        "target_counts": {split: len(target_sets[split]) for split in REQUIRED_SPLITS},
        "targets_missing_from_train": targets_missing_from_train,
        "missing_target_query_shapes": missing_target_shapes,
        "compositional_holdout_families": {
            split: sorted(families)
            for split, families in COMPOSITIONAL_HOLDOUT_FAMILIES.items()
        },
        "ontology_terms_missing_from_train": missing_terms,
        "val_test_target_overlap": sorted(target_sets["val"] & target_sets["test"]),
        "normalized_exact_cross_split_pairs": duplicates["exact"]["cross_split_pairs"],
        "lexical_near_duplicate_threshold": duplicates["threshold"],
        "lexical_near_duplicate_cross_split_pairs": cross_split_near,
        "test_policy": "Reference test is frozen at Stage E and must not guide data, model, or hyperparameter changes.",
    }


def build_manifest(
    release: dict[str, list[dict[str, str]]],
    validation: dict[str, Any],
    audit: dict[str, Any],
) -> dict[str, Any]:
    family_counts = {
        split: len({row["family_id"] for row in release[split]}) for split in REQUIRED_SPLITS
    }
    register_counts = {
        split: dict(sorted(Counter(row["register"] for row in release[split]).items()))
        for split in REQUIRED_SPLITS
    }
    query_shape_counts = {
        split: dict(sorted(Counter(row["query_shape"] for row in release[split]).items()))
        for split in REQUIRED_SPLITS
    }
    return {
        "dataset": "sparql_v2",
        "format_version": 2,
        "status": "stage_e_candidate",
        "schema_fields": sorted(REQUIRED_FIELDS),
        "ontology": str(ONTOLOGY_PATH.relative_to(PROJECT_ROOT)),
        "source": str(SOURCE_PATH.relative_to(PROJECT_ROOT)),
        "normalizer": {
            "name": "normalize_model_input",
            "version": NORMALIZER_VERSION,
        },
        "split": {
            "algorithm": SPLIT_ALGORITHM,
            "seed": SPLIT_SEED,
            "unit": "semantic_family",
            "requested_ratio": {"train": 0.70, "val": 0.15, "test": 0.15},
            "family_quotas_by_query_shape": FAMILY_QUOTAS,
            "compositional_holdout_families": {
                split: sorted(families)
                for split, families in COMPOSITIONAL_HOLDOUT_FAMILIES.items()
            },
        },
        "records": validation["records"],
        "families": sum(family_counts.values()),
        "targets": len(
            {
                row["target"]
                for split in REQUIRED_SPLITS
                for row in release[split]
            }
        ),
        "split_counts": validation["split_counts"],
        "family_counts": family_counts,
        "target_counts": audit["target_counts"],
        "register_counts": register_counts,
        "query_shape_counts": query_shape_counts,
        "target_evaluation_contract": {
            "val_unseen_exact_targets": len(audit["targets_missing_from_train"]["val"]),
            "test_unseen_exact_targets": len(audit["targets_missing_from_train"]["test"]),
            "unseen_target_shapes": sorted(FAMILY_QUOTAS),
            "ontology_terms_missing_from_train": 0,
        },
        "sha256": {
            f"{split}.jsonl": _sha256(DATASET_DIR / f"{split}.jsonl")
            for split in REQUIRED_SPLITS
        }
        | {
            "coverage_draft.jsonl": _sha256(SOURCE_PATH),
            "../../ontology/ontology_v12.ttl": _sha256(ONTOLOGY_PATH),
        },
    }


def write_stage_e_artifacts() -> dict[str, Any]:
    source = load_dataset(SOURCE_PATH)
    stage_d_audit = json.loads((REVIEW_DIR / "stage_d_audit.json").read_text(encoding="utf-8"))
    if _sha256(SOURCE_PATH) != stage_d_audit["target_sha256"]:
        raise ValueError("Stage D coverage draft checksum changed after review")

    release = split_families(source)
    for split in REQUIRED_SPLITS:
        _write_jsonl(DATASET_DIR / f"{split}.jsonl", release[split])

    graph = load_ontology(ONTOLOGY_PATH)
    validation = validate_release(release, graph)
    audit = build_audit(source, release)
    if audit["status"] != "family_split_complete":
        raise ValueError("Stage E split did not pass its review contract")
    manifest = build_manifest(release, validation, audit)
    rendered_manifest = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    MANIFEST_PATH.write_text(rendered_manifest, encoding="utf-8")
    CANDIDATE_MANIFEST_PATH.write_text(rendered_manifest, encoding="utf-8")
    audit["manifest_sha256"] = _sha256(CANDIDATE_MANIFEST_PATH)
    audit["split_sha256"] = {
        split: _sha256(DATASET_DIR / f"{split}.jsonl") for split in REQUIRED_SPLITS
    }
    AUDIT_PATH.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    manifest = write_stage_e_artifacts()
    print(
        "Stage E candidate: "
        + ", ".join(
            f"{split}={manifest['family_counts'][split]} families/{manifest['split_counts'][split]} records"
            for split in REQUIRED_SPLITS
        )
    )


if __name__ == "__main__":
    main()
