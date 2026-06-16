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
# Active ontology = the rebuilt graph (scripts/build_ontology.py is its source of
# truth; this .owl is the generated artifact). Built FROM the v8 source below.
ONTOLOGY_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure.owl"
ONTOLOGY_SOURCE_PATH = ONTOLOGY_DIR / "Ontology_AcademicProcedure_v8.owx"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASET_DIR = RESOURCES / "datasets"
TRAIN_PATH = DATASET_DIR / "train.jsonl"
TEST_PATH = DATASET_DIR / "test.jsonl"


# Artifacts
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "models" / "vit5_tree"
CHECKPOINT_DIR = ARTIFACTS_DIR / "checkpoints"
TRAIN_ARTIFACTS_DIR = ARTIFACTS_DIR / "training"
EVAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "evaluation"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chatbot.log"

# Web UI
WEB_DIR = PROJECT_ROOT / "webui"

# Model — ViT5-base seq2seq (text → cây JSON). Train cục bộ (GPU) phiên sau;
# serve nạp local nếu có, không thì snapshot_download từ HF repo người dùng.
MODEL_NAME = "VietAI/vit5-base"
FINETUNED_MODEL_NAME = "vpthinh19/vit5-academic-tree"   # repo MỚI cho ViT5
MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 256

# Training (dùng ở phiên train ViT5)
EPOCHS = 10
BATCH_SIZE = 16
LEARNING_RATE = 3e-4
VAL_SIZE = 0.2
SEED = 42

# Không có ngưỡng fuzzy cứng (DESIGN.md §9): khớp lấy điểm cao nhất, xem ontology._score.
