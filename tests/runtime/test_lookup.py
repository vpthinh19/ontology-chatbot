"""Ranh giới giữa trợ lý và engine: giới hạn từ khoá, JSON gom theo nguồn, không chặn vòng sự kiện."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from ontchatbot.runtime.lookup import (
    MAX_KEYWORD_CHARACTERS,
    MAX_KEYWORDS_PER_LOOKUP,
    OntologyLookup,
    bound_keywords,
    render_response,
)
from ontchatbot.search import SearchEngine, SearchResponse, TriGFileSource

MINI_ONTOLOGY = Path(__file__).resolve().parents[1] / "fixtures" / "mini-ontology.trig"


@pytest.fixture(scope="module")
def engine() -> SearchEngine:
    return SearchEngine.open(TriGFileSource(MINI_ONTOLOGY))


def test_keywords_are_trimmed_deduplicated_and_bounded() -> None:
    keywords = [" học phí ", "học phí", "", "x" * (MAX_KEYWORD_CHARACTERS + 5)]
    keywords += [f"từ khoá {index}" for index in range(MAX_KEYWORDS_PER_LOOKUP + 3)]

    bounded, notice = bound_keywords(keywords)

    assert bounded[0] == "học phí"
    assert bounded[1] == "x" * MAX_KEYWORD_CHARACTERS
    assert len(bounded) == MAX_KEYWORDS_PER_LOOKUP
    assert notice == {
        "limit": MAX_KEYWORDS_PER_LOOKUP,
        "length": MAX_KEYWORD_CHARACTERS,
        "omitted": 5,
        "shortened": 1,
    }


def test_short_clean_keywords_carry_no_notice() -> None:
    assert bound_keywords(["nghỉ học tạm thời", "bảo lưu"]) == (["nghỉ học tạm thời", "bảo lưu"], None)
    assert bound_keywords("học phí") == (["học phí"], None)


def test_found_results_are_rendered_with_matched_rows_and_facts_inside_their_sources(engine) -> None:
    payload = json.loads(render_response(engine.search(["nghỉ học tạm thời", "bóng đá"])))

    assert payload["status"] == "found"
    top = payload["results"][0]
    assert top["label"] == "Thủ tục nghỉ học tạm thời"
    assert top["classes"] == ["Thủ tục học vụ"]
    assert 1 <= len(top["matched"]) <= 3
    assert all("nghỉ học tạm thời" in row.casefold() for row in top["matched"])
    article = next(group for group in top["sources"]
                   if group["citation"] and group["citation"].startswith("Điều 24"))
    assert article["citation"] == ("Điều 24 Quy chế đào tạo trình độ đại học, "
                                   "ban hành kèm Quyết định 1052/QĐ-ĐHNT ngày 17/7/2025")
    assert article["url"] == "https://example.test/qd-1052.pdf"
    assert {"subject": "Thủ tục nghỉ học tạm thời", "property": "nộp tại",
            "value": "Phòng Công tác sinh viên"} in article["facts"]
    khong_nguon = top["sources"][-1]
    assert khong_nguon["citation"] is None, "nhóm không có nguồn phải xuống cuối"
    assert payload["unmatched"] == ["bóng đá"]


def test_payload_keys_are_plain_english_words() -> None:
    """Khoá JSON đồng bộ với tên gọi trong code: tiếng Anh, không ghép chữ Việt bằng ``_``."""

    payload = json.loads(render_response(SearchResponse(["x"], [], ["x"]), {"omitted": 1}))

    assert set(payload) == {"status", "guidance", "results", "unmatched", "truncation"}


def test_no_result_is_rendered_as_not_found(engine) -> None:
    payload = json.loads(render_response(engine.search(["bóng đá"]), {"omitted": 1}))

    assert payload["status"] == "not_found"
    assert payload["results"] == []
    assert payload["truncation"] == {"omitted": 1}


def test_the_lookup_runs_the_engine_off_the_event_loop_thread() -> None:
    seen = {}

    class Engine:
        def search(self, keywords):
            seen["keywords"] = keywords
            seen["thread"] = threading.get_ident()
            return SearchResponse(list(keywords), [], list(keywords))

    async def run():
        lookup = OntologyLookup(Engine(), workers=1)
        try:
            return await lookup(["học phí", "học phí"]), threading.get_ident()
        finally:
            await lookup.aclose()

    rendered, loop_thread = asyncio.run(run())

    assert seen["keywords"] == ["học phí"]
    assert seen["thread"] != loop_thread
    assert json.loads(rendered)["status"] == "not_found"


def test_the_lookup_needs_at_least_one_worker() -> None:
    with pytest.raises(ValueError):
        OntologyLookup(object(), workers=0)
