"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_ROOT.parent.parent

_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

ONTOLOGY_DIR = RESOURCES / "ontology"
ONTOLOGY_PATH = ONTOLOGY_DIR / "ontology_v12.ttl"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASETS_DIR = RESOURCES / "datasets"
DATASET_DIR = DATASETS_DIR / "sparql_v1"
TRAIN_DATASET_PATH = DATASET_DIR / "train.jsonl"
VAL_DATASET_PATH = DATASET_DIR / "val.jsonl"
TEST_DATASET_PATH = DATASET_DIR / "test.jsonl"
DATASET_MANIFEST_PATH = DATASET_DIR / "manifest.json"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
