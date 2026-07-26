"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_ROOT.parent.parent

_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

ONTOLOGY_DIR = RESOURCES / "ontology"
ONTOLOGY_PATH = ONTOLOGY_DIR / "ontology_v11.ttl"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASET_DIR = RESOURCES / "datasets"
DATASET_PATH = DATASET_DIR / "sparql_v1.jsonl"

BENCHMARK_DIR = RESOURCES / "benchmarks"
BENCHMARK_PATH = BENCHMARK_DIR / "sparql_v1.jsonl"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
