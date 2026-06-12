"""Centralised configuration — paths, model ids, hyper-parameters.

All paths are derived from the package root so the codebase works both as a
source checkout and as an installed wheel.
"""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_ROOT.parent.parent

_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG


# Resources
ONTOLOGY_DIR = RESOURCES / "ontology"
LABEL_MAP_PATH = ONTOLOGY_DIR / "label_map.json"            # v9 class URIs (new graph)
LEGACY_LABEL_MAP_PATH = ONTOLOGY_DIR / "label_map_v8.json"  # v8 class URIs (legacy)
# Active ontology for the new pipeline (graph.py). The legacy ``Ontology``
# class (ontology.py) stays pinned to v8 until step 3 retires it, so its tests
# and any training that reads it are unaffected by the v9 remodel.
ONTOLOGY_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v9.owx"
LEGACY_ONTOLOGY_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v8.owx"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASET_DIR = RESOURCES / "datasets"
TRAIN_PATH = DATASET_DIR / "train.jsonl"
TEST_PATH = DATASET_DIR / "test.jsonl"


# Artifacts
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "models" / "phobert_ner_ft"
CHECKPOINT_DIR = ARTIFACTS_DIR / "checkpoints"
TRAIN_ARTIFACTS_DIR = ARTIFACTS_DIR / "training"
EVAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "evaluation"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chatbot.log"

# Web UI
WEB_DIR = PROJECT_ROOT / "webui"

# Model
MODEL_NAME = "vinai/phobert-base-v2"
FINETUNED_MODEL_NAME = "vpthinh19/phobert-base-v2"
MAX_LENGTH = 128

# Training
EPOCHS = 10
BATCH_SIZE = 32
LEARNING_RATE = 3e-5
VAL_SIZE = 0.2
SEED = 42

# Fuzzy matching
FUZZY_TOP_K = 10
FUZZY_MIN_SCORE = 86.0
