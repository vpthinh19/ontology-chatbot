"""Engine chạy trên ontology thật: mỗi kiểu câu hỏi ra đúng mục, dữ kiện có nguồn."""

from __future__ import annotations

import pytest

from ontchatbot.search import EntryKind, SearchEngine, TriGFileSource
from ontchatbot.settings import ONTOLOGY_PATH


@pytest.fixture(scope="module")
def engine() -> SearchEngine:
    return SearchEngine.open(TriGFileSource(ONTOLOGY_PATH))


def _nodes(response) -> list[str]:
    return [result.node for result in response.results]


def test_a_procedure_is_found_by_its_name(engine) -> None:
    assert _nodes(engine.search(["nghỉ học tạm thời"]))[0] == ":ThuTucNghiHocTamThoi"


def test_an_attribute_is_found_through_its_datatype_property_row(engine) -> None:
    response = engine.search(["điện thoại phòng đào tạo"])

    assert response.results[0].node == ":PhongDaoTaoDaiHoc"
    assert response.results[0].matched[0].entry.kind is EntryKind.DATATYPE_PROPERTY


def test_a_relation_question_reaches_the_office_and_the_procedures_it_receives(engine) -> None:
    """Hồ sơ của phòng liệt kê các thủ tục trỏ tới nó, mỗi cái kèm nguồn riêng."""

    response = engine.search(["thủ tục nộp tại phòng công tác sinh viên"])

    office = next(r for r in response.results if r.node == ":PhongCongTacChinhTriVaSinhVien")
    nguon = {source.citation for source, _ in office.profile.groups if source}
    assert len(nguon) >= 3, "mỗi thủ tục phải mang trích dẫn của chính điều khoản nói ra nó"


def test_every_fact_of_a_procedure_can_be_traced_or_is_marked_uncitable(engine) -> None:
    profile = engine.search(["thủ tục chuyển ngành"]).results[0].profile

    assert profile.groups
    for source, facts in profile.groups:
        assert facts
        if source is not None:
            assert source.citation and source.url


def test_a_table_is_an_entity_people_can_ask_about(engine) -> None:
    """Bảng mang nội dung thật và có tên gọi phụ do người thêm, nên phải tra được."""

    assert _nodes(engine.search(["xếp loại học lực"]))[0] == ":BangXepLoaiHocLuc"


def test_the_source_layer_never_shows_up_as_an_answer(engine) -> None:
    for keyword in ("quy chế đào tạo", "khoản 3 điều 24", "quyết định 1052"):
        for node in _nodes(engine.search([keyword])):
            assert not node.startswith((":Nguon", ":TD")), f"{keyword} ra tầng nguồn: {node}"
