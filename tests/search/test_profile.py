"""Hồ sơ node: dữ kiện của node và thành phần, nguồn theo basedOn, quan hệ chiều ngược."""

from __future__ import annotations

from ontchatbot.search import ACADEMIC, ProfileReader, Source

ARTICLE = Source("Điều 24 Quy chế đào tạo", "https://example.edu.vn/quy-che.pdf")
CLAUSE = Source("khoản 3 Điều 24 Quy chế đào tạo", "https://example.edu.vn/quy-che.pdf")


def test_facts_are_grouped_by_the_source_of_the_node_that_states_them(mini_ontology) -> None:
    profile = ProfileReader(mini_ontology).read(ACADEMIC.LeaveProcedure)
    groups = {sources: [(fact.subject_label, fact.property_label, fact.value) for fact in facts]
              for sources, facts in profile.facts_by_source()}

    assert profile.label == "Thủ tục nghỉ học tạm thời"
    assert profile.classes == ["Thủ tục học vụ"]
    assert ("Thủ tục nghỉ học tạm thời", "nộp tại", "Phòng Công tác Chính trị và Sinh viên") in groups[(ARTICLE,)]
    assert ("Điều kiện nghỉ học tạm thời", "nội dung điều kiện", "Đã học ít nhất một học kỳ.") in groups[(ARTICLE,)]
    assert ("Nghỉ học tạm thời - bước 1", "nội dung bước", "Viết đơn theo Mẫu số 09.") in groups[(CLAUSE,)]


def test_components_follow_their_order_property(mini_ontology) -> None:
    profile = ProfileReader(mini_ontology).read(ACADEMIC.LeaveProcedure)
    step_texts = [fact.value for fact in profile.facts if fact.property_label == "nội dung bước"]

    assert step_texts == ["Viết đơn theo Mẫu số 09.", "Gửi đơn cho Hiệu trưởng."]


def test_source_links_and_component_links_are_not_repeated_as_facts(mini_ontology) -> None:
    profile = ProfileReader(mini_ontology).read(ACADEMIC.LeaveProcedure)
    properties = {fact.property_label for fact in profile.facts}

    assert not properties & {"căn cứ", "trích dẫn", "có bước", "có điều kiện"}


def test_a_node_without_basedon_is_its_own_source_only_when_it_carries_a_citation(mini_ontology) -> None:
    reader = ProfileReader(mini_ontology)

    assert reader.sources(ACADEMIC.Article24) == (ARTICLE,)
    assert reader.sources(ACADEMIC.StudentAffairsOffice) == ()


def test_incoming_relations_are_reported_through_the_entry_node(mini_ontology) -> None:
    """Hai bước cùng trỏ tới Sinh viên được báo một lần, dưới tên thủ tục chứa chúng."""

    reader = ProfileReader(mini_ontology)
    student = [(relation.subject, relation.property_label) for relation in reader.read(ACADEMIC.Student).incoming]
    article = [(relation.subject_label, relation.property_label) for relation in reader.read(ACADEMIC.Article24).incoming]

    assert student == [(":LeaveProcedure", "do ai thực hiện")]
    assert article == [
        ("Thủ tục nghỉ học tạm thời", "căn cứ"),
        ("khoản 3 Điều 24 Quy chế đào tạo", "nằm trong phần"),
    ]
