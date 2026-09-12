"""Hồ sơ thực thể: dữ kiện gom theo cái túi đã khẳng định chúng."""

from __future__ import annotations

from ontchatbot.search import ProfileReader

PROCEDURE = ":ThuTucNghiHocTamThoi"
ARTICLE = "Điều 24 Quy chế đào tạo trình độ đại học, ban hành kèm Quyết định 1052/QĐ-ĐHNT ngày 17/7/2025"
CLAUSE = "khoản 3 Điều 24 Quy chế đào tạo trình độ đại học, ban hành kèm Quyết định 1052/QĐ-ĐHNT ngày 17/7/2025"


def _groups(profile) -> dict[str | None, list[tuple[str, str, str]]]:
    return {source.citation if source else None:
            [(fact.subject_label, fact.property_label, fact.value) for fact in facts]
            for source, facts in profile.groups}


def test_facts_are_grouped_by_the_bag_that_states_them(mini_ontology) -> None:
    profile = ProfileReader(mini_ontology).read(PROCEDURE)
    groups = _groups(profile)

    assert profile.label == "Thủ tục nghỉ học tạm thời"
    assert profile.classes == ["Thủ tục học vụ"]
    assert ("Thủ tục nghỉ học tạm thời", "nộp tại", "Phòng Công tác sinh viên") in groups[ARTICLE]
    assert ("Thủ tục nghỉ học tạm thời", "nội dung",
            "Sinh viên viết đơn theo Mẫu số 09 gửi Hiệu trưởng.") in groups[CLAUSE]


def test_a_citation_joins_the_coordinate_with_the_document_it_sits_in(mini_ontology) -> None:
    """Trích dẫn ghép từ hai tầng, nên đổi số hiệu văn bản là mọi câu đổi theo."""

    source = ProfileReader(mini_ontology).source(":TD1052_D24K3")

    assert source.citation == CLAUSE
    assert source.url == "https://example.test/qd-1052.pdf"


def test_statements_outside_every_bag_carry_no_citation_and_come_last(mini_ontology) -> None:
    """Câu ta tự khẳng định nói ra được nhưng không trích dẫn được, nên xuống cuối."""

    profile = ProfileReader(mini_ontology).read(PROCEDURE)

    source, facts = profile.groups[-1]
    assert source is None
    assert ("Thủ tục nghỉ học tạm thời", "thủ tục tiếp theo", "Thủ tục xin học trở lại") in [
        (f.subject_label, f.property_label, f.value) for f in facts
    ]


def test_a_node_sees_what_other_nodes_say_about_it_with_their_own_source(mini_ontology) -> None:
    """Hỏi ngược từ phòng ban phải ra thủ tục kèm nguồn của chính câu đó, không
    phải nguồn của phòng ban."""

    profile = ProfileReader(mini_ontology).read(":PhongCongTacSinhVien")
    groups = _groups(profile)

    assert ("Thủ tục nghỉ học tạm thời", "nộp tại", "Phòng Công tác sinh viên") in groups[ARTICLE]


def test_the_source_layer_is_never_offered_as_a_fact(mini_ontology) -> None:
    """toaDo và thuocNguon dựng nên trích dẫn; chúng không phải dữ kiện học vụ."""

    profile = ProfileReader(mini_ontology).read(PROCEDURE)

    ten = {fact.property_label for _, facts in profile.groups for fact in facts}
    assert not ten & {"toạ độ", "thuộc nguồn", "số hiệu", "ban hành ngày", "đường dẫn"}
