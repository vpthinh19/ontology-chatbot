"""Centralized configuration for PhoBERT fine-tuning pipeline."""

from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

TRAIN_DATASET_PATH = str(BASE_DIR / "dataset" / "train.jsonl")
TEST_DATASET_PATH = str(BASE_DIR / "dataset" / "test.jsonl")
LABEL_MAP_PATH = str(BASE_DIR / "src" / "utils" / "label_map.json")

MODEL_BCE_DIR = str(BASE_DIR / "models" / "phobert-bce")
MODEL_ASL_DIR = str(BASE_DIR / "models" / "phobert-asl")
MODEL_ZLPR_DIR = str(BASE_DIR / "models" / "phobert-zlpr")

OUTPUT_DIR = str(BASE_DIR / "out")
TRAIN_OUTPUT_DIR = str(BASE_DIR / "out" / "training")
EVAL_OUTPUT_DIR = str(BASE_DIR / "out" / "evaluation")
CHECKPOINT_DIR = str(BASE_DIR / "out" / "checkpoints")

# ONNX configuration
ONNX_DIR = str(BASE_DIR / "models" / "onnx")
ONNX_BCE_PATH = str(BASE_DIR / "models" / "onnx" / "phobert-bce.onnx")
ONNX_ASL_PATH = str(BASE_DIR / "models" / "onnx" / "phobert-asl.onnx")
ONNX_ZLPR_PATH = str(BASE_DIR / "models" / "onnx" / "phobert-zlpr.onnx")

# PhoBERT configuration
MODEL_NAME = "vinai/phobert-base-v2"
MAX_LENGTH = 256

# Training configuration
EPOCHS = 30
BATCH_SIZE = 16
LEARNING_RATE = 3e-5
VAL_SIZE = 0.2

# Asymmetric Loss (Ridnik et al., ICCV 2021)
ASL_GAMMA_POS = 0
ASL_GAMMA_NEG = 4
ASL_CLIP = 0.05

# Randomization
RANDOM_SEED = 42
