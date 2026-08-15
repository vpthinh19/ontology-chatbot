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

DATASET_DIR = RESOURCES / "dataset"
TRAIN_DATASET_PATH = DATASET_DIR / "train.jsonl"
VAL_DATASET_PATH = DATASET_DIR / "val.jsonl"
TEST_DATASET_PATH = DATASET_DIR / "test.jsonl"
PROCEDURE_LANGUAGE_CASES_PATH = RESOURCES / "cases" / "procedure_language.jsonl"
REJECTION_CHECKLIST_PATH = RESOURCES / "cases" / "rejection_checklist.json"
USER_QUERIES_PATH = RESOURCES / "cases" / "user_queries.json"
DATASET_MANIFEST_PATH = DATASET_DIR / "manifest.json"
QUERY_CATALOGUE_PATH = DATASET_DIR / "catalogue.jsonl"
#: Họ truy vấn viết tay: so sánh ngưỡng, tổng hợp nhiều cột, chọn bản ghi phù
#: hợp nhất. Bộ sinh cơ học chỉ dựng được truy vấn đi theo đường dẫn nên không
#: thể tự sinh những họ này; chúng được trộn vào khi dựng lại danh mục.
QUERY_CATALOGUE_MANUAL_PATH = DATASET_DIR / "catalogue-manual.jsonl"
COVERAGE_REQUIREMENTS_PATH = DATASET_DIR / "coverage.json"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
