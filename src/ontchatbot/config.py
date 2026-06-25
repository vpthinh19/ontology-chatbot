"""Centralised configuration - paths, model ids, hyper-parameters.

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
# Ontology hệ thống = MỘT file tự-chứa (8 lớp/7 obj/10 data/54 cá thể + nhãn/alias =
# chìa khoá khớp). Ưu tiên ontology_v9.owx (OWL/XML, nguồn Protégé); fallback
# Ontology_AcademicProcedure.owl (RDF/XML, bản gộp). owlready2
# nạp cả hai như nhau (đã xác minh: cùng 8 lớp/54 cá thể/7 obj/10 data).
# Provenance cách dựng nhãn/alias: dev/ontology_build/.
ONTOLOGY_PATH = (
    ONTOLOGY_DIR / "ontology_v9.owx"
    if (ONTOLOGY_DIR / "ontology_v9.owx").exists()
    else ONTOLOGY_DIR / "Ontology_AcademicProcedure.owl"
)
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASET_DIR = RESOURCES / "datasets"
TRAIN_PATH = DATASET_DIR / "train.jsonl"
TEST_PATH = DATASET_DIR / "test.jsonl"

# Khâu dựng dataset (catalog/Codex/oracle) đã chuyển sang dev/dataset_construction/
# (dev-only, gitignored); đường dẫn của nó ở dev/dataset_construction/_paths.py.


# Artifacts
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR = ARTIFACTS_DIR / "models" / "bartpho_tree"
EVAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "evaluation"
TRAINING_ARTIFACTS_DIR = ARTIFACTS_DIR / "training"
# log_history (loss/eval_loss theo bước) train.py lưu sau khi train → Hình 8 đường cong huấn luyện.
TRAIN_LOG_PATH = TRAINING_ARTIFACTS_DIR / "log_history.json"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chatbot.log"

# Hình trực quan cho docs/CONCEPT.md (eval: train-curve/per-category/confusion; benchmark: per-type/recall@k).
FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"

# Web UI
WEB_DIR = PROJECT_ROOT / "webui"

# Model - BARTpho-syllable seq2seq (text → cây JSON). Serve nạp model CTranslate2 cục bộ nếu có,
# không thì snapshot_download từ HF repo. BARTpho là mBART (encoder-decoder),
#  KHÁC T5: inference qua ctranslate2.Translator (xem model.py), KHÔNG dùng generate().
MODEL_NAME = "vinai/bartpho-syllable"
FINETUNED_MODEL_NAME = "vpthinh19/bartpho-ontology"    # repo HF cho bartpho fine-tuned
MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 256

# Inference deploy - CTranslate2 (thay ONNX: gọn cho encoder+decoder, CPU int8 nhanh).
# Convert: thêm `config.normalize_before = True` (pretrained thiếu → CT2 sinh rác nếu
# bỏ qua) rồi TransformersConverter(quantization="int8"). Thư mục model CT2 sau convert:
CT2_MODEL_DIR = ARTIFACTS_DIR / "models" / "bartpho_ct2"
CT2_QUANTIZATION = "int8"

# Training (dùng ở phiên train BARTpho)
EPOCHS = 10
BATCH_SIZE = 8
GRAD_ACCUM = 1
LEARNING_RATE = 3e-5
VAL_SIZE = 0.2
SEED = 42

