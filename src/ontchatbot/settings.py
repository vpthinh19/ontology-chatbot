"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

#: Điểm cuối mặc định của dịch vụ LLM tương thích giao thức OpenAI.
DEFAULT_LLM_BASE_URL = "https://lightning.ai/api/v1/"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = PROJECT_ROOT / "resources" / "ontology" / "ontology.trig"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"
