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
from ontchatbot.search import SearchEngine, SearchResponse, TurtleFileSource

MINI_ONTOLOGY = Path(__file__).resolve().parents[1] / "fixtures" / "mini-ontology.ttl"


@pytest.fixture(scope="module")
def engine() -> SearchEngine:
    return SearchEngine.open(TurtleFileSource(MINI_ONTOLOGY))


def test_keywords_are_trimmed_deduplicated_and_bounded() -> None:
    keywords = [" học phí ", "học phí", "", "x" * (MAX_KEYWORD_CHARACTERS + 5)]
    keywords += [f"từ khoá {index}" for index in range(MAX_KEYWORDS_PER_LOOKUP + 3)]

    bounded, notice = bound_keywords(keywords)

    assert bounded[0] == "học phí"
    assert bounded[1] == "x" * MAX_KEYWORD_CHARACTERS
    assert len(bounded) == MAX_KEYWORDS_PER_LOOKUP
    assert notice == {
        "so_luong_toi_da": MAX_KEYWORDS_PER_LOOKUP,
        "do_dai_toi_da": MAX_KEYWORD_CHARACTERS,
        "so_luong_bo_qua": 5,
        "so_luong_rut_gon": 1,
    }


def test_short_clean_keywords_carry_no_notice() -> None:
    assert bound_keywords(["nghỉ học tạm thời", "bảo lưu"]) == (["nghỉ học tạm thời", "bảo lưu"], None)
    assert bound_keywords("học phí") == (["học phí"], None)


def test_found_results_are_rendered_with_matched_rows_and_facts_inside_their_sources(engine) -> None:
    payload = json.loads(render_response(engine.search(["nghỉ học tạm thời", "bóng đá"])))

    assert payload["trang_thai"] == "co_ket_qua"
    top = payload["ket_qua"][0]
    assert top["muc"] == "Thủ tục nghỉ học tạm thời"
    assert top["loai"] == ["Thủ tục học vụ"]
    assert 1 <= len(top["dong_khop"]) <= 3
    assert all("nghỉ học tạm thời" in row.casefold() for row in top["dong_khop"])
    article = next(group for group in top["nguon"] if group["trich_dan"] == "Điều 24 Quy chế đào tạo")
    assert article["duong_dan"] == "https://example.edu.vn/quy-che.pdf"
    assert {"muc": "Thủ tục nghỉ học tạm thời", "thuoc_tinh": "nộp tại",
            "gia_tri": "Phòng Công tác Chính trị và Sinh viên"} in article["du_lieu"]
    assert payload["tu_khoa_khong_thay"] == ["bóng đá"]


def test_no_result_is_rendered_as_no_information(engine) -> None:
    payload = json.loads(render_response(engine.search(["bóng đá"]), {"so_luong_bo_qua": 1}))

    assert payload["trang_thai"] == "khong_co_thong_tin"
    assert payload["ket_qua"] == []
    assert payload["tu_khoa_da_cat"] == {"so_luong_bo_qua": 1}


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
    assert json.loads(rendered)["trang_thai"] == "khong_co_thong_tin"


def test_the_lookup_needs_at_least_one_worker() -> None:
    with pytest.raises(ValueError):
        OntologyLookup(object(), workers=0)
