"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_ROOT.parent.parent

_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

ONTOLOGY_DIR = RESOURCES / "ontology"
ONTOLOGY_PATH = ONTOLOGY_DIR / "ontology.ttl"
ANSWER_INVENTORY_PATH = ONTOLOGY_DIR / "answer_inventory.json"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASET_DIR = RESOURCES / "dataset" / "main"
TRAIN_DATASET_PATH = DATASET_DIR / "train.jsonl"
VAL_DATASET_PATH = DATASET_DIR / "val.jsonl"
TEST_DATASET_PATH = DATASET_DIR / "test.jsonl"
PROCEDURE_LANGUAGE_CASES_PATH = RESOURCES / "cases" / "procedure_language.jsonl"
DATASET_MANIFEST_PATH = DATASET_DIR / "manifest.json"
QUERY_CATALOGUE_PATH = DATASET_DIR / "catalogue.jsonl"
COVERAGE_REQUIREMENTS_PATH = DATASET_DIR / "coverage.json"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
