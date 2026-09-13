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
ONTOLOGY_PATH = ONTOLOGY_DIR / "ontology.trig"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"

#: Chỉ mục tìm kiếm lưu ra đĩa bởi ``ontology_search build`` để xem và so sánh. Dịch vụ tự
#: dựng chỉ mục trong bộ nhớ lúc khởi động nên không cần thư mục này.
SEARCH_INDEX_DIR = PROJECT_ROOT / "build" / "search-index"
