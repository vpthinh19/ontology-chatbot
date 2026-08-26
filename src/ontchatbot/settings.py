"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

#: Điểm cuối mặc định của dịch vụ LLM tương thích giao thức OpenAI.
DEFAULT_LLM_BASE_URL = "https://lightning.ai/api/v1/"

PKG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PKG_ROOT.parent.parent

_RESOURCES_DEV = PROJECT_ROOT / "resources"
_RESOURCES_PKG = PKG_ROOT / "resources"
RESOURCES = _RESOURCES_DEV if _RESOURCES_DEV.is_dir() else _RESOURCES_PKG

ONTOLOGY_DIR = RESOURCES / "ontology"
ONTOLOGY_PATH = ONTOLOGY_DIR / "ontology.ttl"
ANSWER_INVENTORY_PATH = ONTOLOGY_DIR / "answer_inventory.json"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

DATASET_DIR = RESOURCES / "dataset"
TRAIN_DATASET_PATH = DATASET_DIR / "train.jsonl"
VAL_DATASET_PATH = DATASET_DIR / "val.jsonl"
TEST_DATASET_PATH = DATASET_DIR / "test.jsonl"
#: Nguồn gốc của dataset: khung ý định, câu từ chối, câu viết tay và quan hệ
#: giữa khung với câu được sinh. Các phép kiểm dùng chúng để xác minh dataset.
PROVENANCE_DIR = RESOURCES / "provenance"
FRAMES_PATH = PROVENANCE_DIR / "frames.jsonl"
REJECTION_FRAMES_PATH = PROVENANCE_DIR / "rejections.jsonl"
WRITTEN_QUESTIONS_PATH = PROVENANCE_DIR / "written-questions.jsonl"
REJECTION_CHECKLIST_PATH = PROVENANCE_DIR / "rejection_checklist.json"
REJECTION_PROVENANCE_PATH = PROVENANCE_DIR / "rejection_provenance.json"

#: Câu hỏi thực tế, được đánh giá riêng và không thuộc train/val/test.
USER_QUERIES_PATH = RESOURCES / "cases" / "user_queries.json"
USER_QUERIES_TEXT_PATH = RESOURCES / "cases" / "user_queries.txt"
DATASET_MANIFEST_PATH = DATASET_DIR / "manifest.json"
#: Danh mục truy vấn là cấu hình runtime dùng để xác định các truy vấn hợp lệ,
#: không phải dữ liệu huấn luyện.
QUERY_CATALOGUE_PATH = ONTOLOGY_DIR / "catalogue.jsonl"
#: Họ truy vấn thủ công cho các phép so sánh, tổng hợp và lựa chọn bản ghi.
QUERY_CATALOGUE_MANUAL_PATH = ONTOLOGY_DIR / "catalogue-manual.jsonl"
COVERAGE_REQUIREMENTS_PATH = DATASET_DIR / "coverage.json"

#: Thư mục gốc cho lượt huấn luyện và model chuyển đổi cục bộ.
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
#: Báo cáo dẫn xuất được dùng làm đối chứng để phát hiện trôi lệch nguồn.
REPORTS_DIR = RESOURCES / "reports"
