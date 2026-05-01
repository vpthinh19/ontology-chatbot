"""Centralised configuration: paths, model identifiers, hyperparameters.

The package follows the *src-layout*; every filesystem path is computed relative
to the project root so the package is location-agnostic.
"""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_ROOT.parent.parent

# Static resources (label map, ontology) live outside the package and are
# referenced by absolute path; for installed wheels the same files are copied
# under ``ontchatbot/resources``.
_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

LABEL_MAP_PATH = RESOURCES / "label_map.json"
ONTOLOGY_PATH = RESOURCES / "Ontology_AcademicProcedure_v6.owx"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

# Generated artefacts
DATASET_DIR = PROJECT_ROOT / "dataset"
TRAIN_PATH = DATASET_DIR / "train.jsonl"
TEST_PATH = DATASET_DIR / "test.jsonl"

OUT_DIR = PROJECT_ROOT / "out"
MODEL_DIR = PROJECT_ROOT / "models" / "phobert-ner"
TRAIN_OUT_DIR = OUT_DIR / "training"
EVAL_OUT_DIR = OUT_DIR / "evaluation"

WEB_DIR = PROJECT_ROOT / "web"

# Model
MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 128

# Training
EPOCHS = 20
BATCH_SIZE = 16
LEARNING_RATE = 3e-5
WEIGHT_DECAY = 0.005
WARMUP_STEPS = 0.1
VAL_SIZE = 0.2
SEED = 42

# Inference
FUZZY_TOP_K = 5
FUZZY_MIN_SCORE = 55.0

# Greeting heuristic — case- and diacritic-insensitive substrings
GREETING_KEYWORDS: tuple[str, ...] = (
    "xin chao", "chao", "hello", "hi ", "hey", "alo",
    "cam on", "thanks", "tks", "tam biet", "bye",
)
