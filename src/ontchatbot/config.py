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
# Ontology hệ thống = MỘT file tự-chứa (8 lớp/7 obj/10 data/54 cá thể + nhãn/alias =
# chìa khoá khớp). Ưu tiên .owx (OWL/XML, nguồn Protégé); fallback .owl (RDF/XML) là bản
# gộp cho tới khi Save-As .owx trong Protégé. owlready2 nạp cả hai như nhau.
# Provenance cách dựng nhãn/alias: dev/ontology_build/.
ONTOLOGY_PATH = (
    ONTOLOGY_DIR / "Ontology_AcademicProcedure.owx"
    if (ONTOLOGY_DIR / "Ontology_AcademicProcedure.owx").exists()
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
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "chatbot.log"

# Web UI
WEB_DIR = PROJECT_ROOT / "webui"

# Model — BARTpho-syllable seq2seq (text → cây JSON). Train cục bộ (GPU) phiên sau;
# serve nạp model CTranslate2 cục bộ nếu có, không thì snapshot_download từ HF repo.
# (Đổi từ ViT5 → bartpho-syllable 2026-06-18: benchmark tương đương trên dataset chuẩn,
#  tác giả VinAI nổi tiếng — cùng nhóm PhoBERT.) BARTpho là mBART (encoder-decoder),
#  KHÁC T5: inference qua ctranslate2.Translator (xem model.py), KHÔNG dùng generate().
MODEL_NAME = "vinai/bartpho-syllable"
FINETUNED_MODEL_NAME = "vpthinh19/bartpho-ontology"    # repo HF cho bartpho fine-tuned
MAX_SOURCE_LENGTH = 128
MAX_TARGET_LENGTH = 256

# Inference deploy — CTranslate2 (thay ONNX: gọn cho encoder+decoder, CPU int8 nhanh).
# Convert: thêm `config.normalize_before = True` (pretrained thiếu → CT2 sinh rác nếu
# bỏ qua) rồi TransformersConverter(quantization="int8"). Thư mục model CT2 sau convert:
CT2_MODEL_DIR = ARTIFACTS_DIR / "models" / "bartpho_ct2"
CT2_QUANTIZATION = "int8"

# Training (dùng ở phiên train BARTpho)
EPOCHS = 10
BATCH_SIZE = 8
LEARNING_RATE = 3e-5
VAL_SIZE = 0.2
SEED = 42

