import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from ontchatbot.research.dataset import REQUIRED_SPLITS, load_dataset, validate_release
from ontchatbot.research.stage_e import (
    AUDIT_PATH,
    COMPOSITIONAL_HOLDOUT_FAMILIES,
    DATASET_DIR,
    FAMILY_QUOTAS,
    MANIFEST_PATH,
    ONTOLOGY_PATH,
    SOURCE_PATH,
    SPLIT_ALGORITHM,
    SPLIT_SEED,
    build_audit,
    split_families,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import PROJECT_ROOT


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_stage_e_split_is_reproducible_and_preserves_every_record() -> None:
    source = load_dataset(SOURCE_PATH)
    expected = split_families(source)
    actual = {
        split: load_dataset(DATASET_DIR / f"{split}.jsonl") for split in REQUIRED_SPLITS
    }

    assert actual == expected
    assert {split: len(actual[split]) for split in REQUIRED_SPLITS} == {
        "train": 656,
        "val": 140,
        "test": 140,
    }
    assert {
        row["id"] for row in source
    } == {
        row["id"] for split in REQUIRED_SPLITS for row in actual[split]
    }


def test_stage_e_keeps_families_whole_and_meets_shape_quotas() -> None:
    release = {
        split: load_dataset(DATASET_DIR / f"{split}.jsonl") for split in REQUIRED_SPLITS
    }
    family_locations: dict[str, set[str]] = defaultdict(set)
    for split, rows in release.items():
        for row in rows:
            family_locations[row["family_id"]].add(split)

    assert len(family_locations) == 234
    assert all(len(locations) == 1 for locations in family_locations.values())
    for split, rows in release.items():
        families = {row["family_id"] for row in rows}
        assert len(families) == {"train": 164, "val": 35, "test": 35}[split]
        assert Counter(row["register"] for row in rows) == {
            register: len(families)
            for register in ("formal", "neutral", "colloquial", "noisy")
        }
        shape_by_family = {
            family: next(row["query_shape"] for row in rows if row["family_id"] == family)
            for family in families
        }
        assert Counter(shape_by_family.values()) == {
            shape: quotas[split] for shape, quotas in FAMILY_QUOTAS.items()
        }


def test_stage_e_release_executes_without_leakage() -> None:
    release = {
        split: load_dataset(DATASET_DIR / f"{split}.jsonl") for split in REQUIRED_SPLITS
    }
    graph = load_ontology(ONTOLOGY_PATH)
    report = validate_release(release, graph)

    assert report["records"] == 936
    assert report["split_counts"] == {"train": 656, "val": 140, "test": 140}
    assert all(not report["splits"][split]["empty_result_ids"] for split in REQUIRED_SPLITS)


def test_stage_e_compositional_holdout_is_explicit_and_schema_seen() -> None:
    release = {
        split: load_dataset(DATASET_DIR / f"{split}.jsonl") for split in REQUIRED_SPLITS
    }
    audit = build_audit(load_dataset(SOURCE_PATH), release)

    assert audit["status"] == "family_split_complete"
    assert audit["targets_missing_from_train"] == {
        split: sorted(
            {
                row["target"]
                for row in release[split]
                if row["family_id"] in COMPOSITIONAL_HOLDOUT_FAMILIES[split]
            }
        )
        for split in ("val", "test")
    }
    assert audit["missing_target_query_shapes"] == {
        split: sorted(FAMILY_QUOTAS) for split in ("val", "test")
    }
    assert audit["ontology_terms_missing_from_train"] == {"val": [], "test": []}
    assert audit["val_test_target_overlap"] == []
    assert audit["normalized_exact_cross_split_pairs"] == 0
    assert audit["lexical_near_duplicate_cross_split_pairs"] == []


def test_stage_e_does_not_reuse_legacy_test_records() -> None:
    candidate_test_ids = {
        row["id"] for row in load_dataset(DATASET_DIR / "test.jsonl")
    }
    legacy_test_ids = {
        row["id"]
        for row in load_dataset(PROJECT_ROOT / "resources/datasets/sparql_v1/test.jsonl")
    }
    source_ids = {row["id"] for row in load_dataset(SOURCE_PATH)}

    assert candidate_test_ids <= source_ids
    assert candidate_test_ids.isdisjoint(legacy_test_ids)


def test_stage_e_manifest_and_audit_lock_the_candidate() -> None:
    manifest = _read_json(MANIFEST_PATH)
    audit = _read_json(AUDIT_PATH)

    assert manifest["status"] == "stage_e_candidate"
    assert manifest["split"]["algorithm"] == SPLIT_ALGORITHM
    assert manifest["split"]["seed"] == SPLIT_SEED
    assert manifest["split"]["compositional_holdout_families"] == {
        split: sorted(families)
        for split, families in COMPOSITIONAL_HOLDOUT_FAMILIES.items()
    }
    assert manifest["records"] == 936
    assert manifest["families"] == 234
    assert manifest["targets"] == 102
    assert manifest["target_evaluation_contract"] == {
        "val_unseen_exact_targets": 5,
        "test_unseen_exact_targets": 5,
        "unseen_target_shapes": sorted(FAMILY_QUOTAS),
        "ontology_terms_missing_from_train": 0,
    }
    for split in REQUIRED_SPLITS:
        assert manifest["sha256"][f"{split}.jsonl"] == _sha256(
            DATASET_DIR / f"{split}.jsonl"
        )
    assert manifest["sha256"]["coverage_draft.jsonl"] == _sha256(SOURCE_PATH)
    assert manifest["sha256"]["../../ontology/ontology_v12.ttl"] == _sha256(
        ONTOLOGY_PATH
    )
    assert audit["manifest_sha256"] == _sha256(MANIFEST_PATH)
    assert audit["source_sha256"] == _sha256(SOURCE_PATH)
