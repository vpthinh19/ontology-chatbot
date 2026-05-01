"""Centralized configuration: paths, model identifiers, training hyperparameters.

All filesystem paths are derived from the project root so the package is relocatable.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Data
DATASET_DIR = ROOT / "dataset"
TRAIN_PATH = DATASET_DIR / "train.jsonl"
TEST_PATH = DATASET_DIR / "test.jsonl"
LABEL_MAP_PATH = ROOT / "src" / "utils" / "label_map.json"

# Ontology
ONTOLOGY_PATH = ROOT / "ontology" / "Ontology_AcademicProcedure_v6.owx"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

# Outputs
OUT_DIR = ROOT / "out"
MODEL_DIR = ROOT / "models" / "phobert-ner"
TRAIN_OUT_DIR = OUT_DIR / "training"
EVAL_OUT_DIR = OUT_DIR / "evaluation"

# Web
WEB_DIR = ROOT / "web"

# Model
MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 128

# Training
EPOCHS = 20
BATCH_SIZE = 16
LEARNING_RATE = 3e-5
WEIGHT_DECAY = 0.001
WARMUP_STEPS = 0.1
VAL_SIZE = 0.2
SEED = 42

# Inference / fuzzy
FUZZY_TOP_K = 5
FUZZY_MIN_SCORE = 55  # below this, treat as out-of-domain (NgoaiLe)
INTENT_GREETING_KEYWORDS = (
    "xin chao", "xin chào", "chao", "chào", "hello", "hi", "hey",
    "cam on", "cảm ơn", "thanks", "tks", "tam biet", "tạm biệt", "bye",
)
