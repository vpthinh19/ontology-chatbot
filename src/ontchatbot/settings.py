"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

#: Điểm cuối mặc định của dịch vụ LLM tương thích giao thức OpenAI.
DEFAULT_LLM_BASE_URL = "https://lightning.ai/api/v1/"
#: Mô hình dự phòng cùng nhà cung cấp, dùng khi mô hình chính không trả lời. Đều đã thử gọi công cụ được.
#: (``openai/gpt-5.6-luna`` KHÔNG dùng được: Lightning báo "Function tools with reasoning_effort are not supported".)
DEFAULT_LLM_FALLBACK_MODELS = ("lightning-ai/Qwen3.8-27B", "google/gemini-3.1-flash-lite-preview")
#: Nhà cung cấp dự phòng cuối: Gemini của Google AI Studio, cũng nói giao thức OpenAI.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
#: Rẻ và đủ mạnh cho việc này; xem ghi chú chọn mô hình trong README của dự án.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = PROJECT_ROOT / "resources" / "ontology" / "ontology.trig"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"
