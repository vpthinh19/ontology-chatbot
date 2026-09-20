"""Đường dẫn và namespace dùng chung."""

from __future__ import annotations

from pathlib import Path

#: Điểm cuối mặc định của dịch vụ LLM tương thích giao thức OpenAI.
DEFAULT_LLM_BASE_URL = "https://lightning.ai/api/v1/"
#: Mô hình dự phòng CÙNG NHÀ Lightning: để trống, vì một sự cố của Lightning thường làm cả nhà im lặng,
#: và mỗi mô hình ở đây đều tính tiền. Chuỗi đi thẳng sang Google AI Studio bên dưới.
#: Ba mô hình đã cân nhắc rồi loại: ``lightning-ai/Qwen3.8-27B`` (trả lời được nhưng đắt và hay chen chữ
#: Trung Quốc), ``openai/gpt-5.6-luna`` (Lightning báo "Function tools with reasoning_effort are not
#: supported"), ``google/gemini-3.1-flash-lite-preview`` (Lightning không chuyển tiếp chữ ký suy nghĩ mà
#: Gemini 3 đòi lại, nên lượt trả kết quả tra cứu về luôn bị từ chối).
#: Đặt ``ONTCHATBOT_LLM_FALLBACK_MODELS`` (ngăn bằng dấu phẩy) để thêm lại khi cần.
DEFAULT_LLM_FALLBACK_MODELS: tuple[str, ...] = ()
#: Nhà cung cấp dự phòng cuối: Gemini của Google AI Studio, cũng nói giao thức OpenAI.
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
#: Rẻ và đủ mạnh cho việc này; xem ghi chú chọn mô hình trong README của dự án.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_PATH = PROJECT_ROOT / "resources" / "ontology" / "ontology.trig"
ONTOLOGY_NS = "http://www.ntu.edu.vn/ontology/academic#"
