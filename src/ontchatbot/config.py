"""Centralised configuration — paths, model ids, hyper-parameters.

All paths are derived from the package root so the codebase works both as a
source checkout and as an installed wheel.
"""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent       # src/ontchatbot/
PROJECT_ROOT = PKG_ROOT.parent.parent             # repo root

# Static resources (label map, ontology). When installed as a wheel the same
# files are copied under ``ontchatbot/resources``.
_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

ONTOLOGY_DIR = RESOURCES / "ontology"
LABEL_MAP_PATH = ONTOLOGY_DIR / "label_map.json"
ONTOLOGY_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v8.owx"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

# Static training data shipped with the package — bundled under
# ``resources/datasets/`` so installed wheels travel with the JSONL.
DATASET_DIR = RESOURCES / "datasets"
TRAIN_PATH = DATASET_DIR / "train.jsonl"
TEST_PATH = DATASET_DIR / "test.jsonl"

ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = PROJECT_ROOT / "models" / "phobert_ner_ft"
TRAIN_ARTIFACTS_DIR = ARTIFACTS_DIR / "training"
EVAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "evaluation"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chatbot.log"

WEB_DIR = PROJECT_ROOT / "webui"

# Model
MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 128

# Training
EPOCHS = 10
BATCH_SIZE = 8
LEARNING_RATE = 2e-5
VAL_SIZE = 0.2
SEED = 42

# Inference — fuzzy threshold tuned at 88: high enough to reject visual
# collisions like "rớt môn" ↔ "rút môn" (≈86 via token_set_ratio) yet low
# enough to keep every perfect-alias match (score 100) — including
# ambiguous cohort spans like "k65" that legitimately resolve to multiple
# fee categories.
FUZZY_TOP_K = 8
FUZZY_MIN_SCORE = 88.0

# Greeting heuristic and rendering policies live in :mod:`renderer` since
# they are presentation concerns. Pipeline and Ontology import them from
# there.
