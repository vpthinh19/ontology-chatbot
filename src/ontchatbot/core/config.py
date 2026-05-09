"""Centralised configuration: paths, model identifiers, hyper-parameters.

Every filesystem path is derived from the project root so the package is
location-agnostic (works both as a checked-out source tree and as an
installed wheel).
"""

from __future__ import annotations

from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = PKG_ROOT.parent.parent

# Static resources (label map, ontology). When installed as a wheel the same
# files are copied under ``ontchatbot/resources``.
_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

LABEL_MAP_PATH = RESOURCES / "label_map.json"
ONTOLOGY_PATH = RESOURCES / "Ontology_AcademicProcedure_v8.owx"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

# Generated artefacts
DATASET_DIR = PROJECT_ROOT / "dataset"
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

# Inference
FUZZY_TOP_K = 5
FUZZY_MIN_SCORE = 55.0

# Greeting heuristic — case- and diacritic-insensitive substrings
GREETING_KEYWORDS: tuple[str, ...] = (
    "xin chao", "chao", "hello", "hi ", "hey", "alo",
    "cam on", "thanks", "tks", "tam biet", "bye",
)
