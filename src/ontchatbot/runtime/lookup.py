"""Công cụ tra cứu của trợ lý: từ khoá vào, kết quả tìm kiếm có nguồn ra.

Lớp này là ranh giới giữa mô hình ngôn ngữ và engine tìm kiếm. Nó giới hạn đầu vào,
chạy engine ở luồng riêng để không chặn vòng sự kiện của máy chủ, và viết kết quả
thành JSON gọn mà mô hình đọc được.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..search import SearchEngine, SearchResponse

logger = logging.getLogger(__name__)

#: Công cụ chỉ cần vài cách gọi ngắn của cùng một ý; 20 từ khoá đã rộng hơn nhiều.
MAX_KEYWORDS_PER_LOOKUP = 20
#: 120 ký tự chặn một câu hỏi dài bị gửi nguyên vào công cụ, mà vẫn rộng hơn tên thủ tục dài nhất.
MAX_KEYWORD_CHARACTERS = 120

FOUND = "found"
NOT_FOUND = "not_found"
_FOUND_GUIDANCE = (
    "Mỗi phần tử của results là một mục của ontology. Kiểm matched trước: nếu không "
    "đúng thứ người dùng hỏi thì coi như không tìm thấy. Dữ kiện nằm trong nguồn đã "
    "khẳng định chúng; đọc hết facts trước khi trả lời."
)
_NOT_FOUND_GUIDANCE = "Không có mục nào khớp. Có thể thử lại một lần với cách gọi khác hẳn; vẫn không có thì dừng."


def bound_keywords(keywords: Sequence[str] | str) -> tuple[list[str], dict[str, int] | None]:
    """Bỏ từ khoá rỗng và trùng, cắt từ khoá quá dài, giữ tối đa ``MAX_KEYWORDS_PER_LOOKUP``."""

    raw = [keywords] if isinstance(keywords, str) else list(keywords)
    shortened = 0
    cleaned: list[str] = []
    for keyword in raw:
        if not isinstance(keyword, str) or not keyword.strip():
            continue
        keyword = keyword.strip()
        if len(keyword) > MAX_KEYWORD_CHARACTERS:
            keyword = keyword[:MAX_KEYWORD_CHARACTERS].rstrip()
            shortened += 1
        cleaned.append(keyword)
    unique = list(dict.fromkeys(cleaned))
    omitted = max(0, len(unique) - MAX_KEYWORDS_PER_LOOKUP)
    truncation = None
    if omitted or shortened:
        truncation = {
            "limit": MAX_KEYWORDS_PER_LOOKUP,
            "length": MAX_KEYWORD_CHARACTERS,
            "omitted": omitted,
            "shortened": shortened,
        }
    return unique[:MAX_KEYWORDS_PER_LOOKUP], truncation


def render_response(response: SearchResponse, truncation: dict[str, int] | None = None) -> str:
    """Viết kết quả tìm kiếm thành JSON cho mô hình: dữ kiện gom theo nguồn."""

    payload: dict[str, object] = {
        "status": FOUND if response.results else NOT_FOUND,
        "guidance": _FOUND_GUIDANCE if response.results else _NOT_FOUND_GUIDANCE,
        "results": [
            {
                "label": result.label,
                "classes": result.profile.classes,
                "matched": [hit.entry.text for hit in result.matched[:3]],
                "sources": [
                    {
                        "citation": " · ".join(source.citation for source in sources) or None,
                        "url": " · ".join(source.url for source in sources if source.url) or None,
                        "facts": [
                            {"subject": fact.subject_label, "property": fact.property_label, "value": fact.value}
                            for fact in facts
                        ],
                    }
                    for sources, facts in result.profile.facts_by_source()
                ],
                "incoming": [
                    {"subject": relation.subject_label, "property": relation.property_label}
                    for relation in result.profile.incoming
                ],
            }
            for result in response.results
        ],
    }
    if response.unmatched_keywords:
        payload["unmatched"] = response.unmatched_keywords
    if truncation is not None:
        payload["truncation"] = truncation
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class OntologyLookup:
    """Hàm tra cứu mà vòng trợ lý gọi: ``await lookup(keywords) -> str``."""

    def __init__(self, engine: SearchEngine, *, workers: int = 4) -> None:
        if workers < 1:
            raise ValueError("workers must be positive")
        self.engine = engine
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ontology-search")

    async def __call__(self, keywords: Sequence[str] | str) -> str:
        bounded, truncation = bound_keywords(keywords)
        started = time.perf_counter()
        response = await asyncio.get_running_loop().run_in_executor(self._executor, self.engine.search, bounded)
        logger.info(
            "lookup keywords=%d results=%d unmatched=%d duration_ms=%.1f",
            len(bounded),
            len(response.results),
            len(response.unmatched_keywords),
            (time.perf_counter() - started) * 1000,
        )
        return render_response(response, truncation)

    async def aclose(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
