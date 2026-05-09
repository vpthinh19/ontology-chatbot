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

# Inference
# ``FUZZY_MIN_SCORE`` is the threshold above which an individual surface is
# admitted as a match. Tuned empirically against the v8 ontology aliases:
# 80 is high enough to reject incidental shared-word overlaps (e.g. an
# alias of *Quy trình bảo lưu* mentioning "học phí" no longer steals the
# *đóng học phí* span) yet low enough that ambiguous cohort spans like
# "k65" still recover both ``Phi_K65_550k`` and ``Phi_K65_620k``.
FUZZY_TOP_K = 8
FUZZY_MIN_SCORE = 80.0

# Greeting heuristic — case- and diacritic-insensitive substrings
GREETING_KEYWORDS: tuple[str, ...] = (
    "xin chao", "chao", "hello", "hi ", "hey", "alo",
    "cam on", "thanks", "tks", "tam biet", "bye",
)

# Rendering — one source of truth for the (small) schema-aware exceptions.
# Everything else (section headers, ordering basis, URL detection) is derived
# from the ontology itself.
#
# ``RENDER_PROPERTY_ORDER`` defines a stable rendering order; properties not
# listed here are appended alphabetically so adding a new property in Protégé
# never requires a code change. ``RENDER_PARAGRAPH_PROPERTIES`` are emitted
# without a bullet header (free-flow descriptions read better that way), and
# ``RENDER_SKIP_PROPERTIES`` are fully suppressed (aliases are matcher input,
# not user-facing content; rdfs:label is consumed as the block title).
RENDER_PARAGRAPH_PROPERTIES: tuple[str, ...] = (
    "procedureDescription", "feeNote",
)
RENDER_SKIP_PROPERTIES: tuple[str, ...] = (
    "hasAlias", "label",
)
RENDER_PROPERTY_ORDER: tuple[str, ...] = (
    # paragraphs come first by convention
    "procedureDescription", "feeNote",
    # individual data properties (logical order: identity → contact → fee)
    "appliesToTarget", "feePerCredit",
    "headOfOffice", "officeLocation",
    "officeEmail", "officePhoneNumber", "officeWebsite",
    "formUrl",
    # object properties — logical "who/what" before "rules/outputs"
    "handledBy", "executedVia",
    "basedOnRegulation",
    "hasCondition", "requiresDocument", "hasStep",
    "hasFeeCategory", "hasPaymentMethod", "hasOutput",
)

# Per-class header emoji. Optional — unknown classes get a neutral bullet.
RENDER_CLASS_EMOJI: dict[str, str] = {
    "AcademicProcedure": "📘",
    "AdministrativeOffice": "🏢",
    "Document": "📄",
    "FeeCategory": "💰",
    "PaymentMethod": "💳",
    "Regulation": "📜",
    "Condition": "✅",
    "OutputResult": "🏁",
}
