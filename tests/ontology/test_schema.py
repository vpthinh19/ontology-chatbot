"""Lược đồ của đồ thị đã lắp phải tự mô tả đầy đủ.

``catalogue_validation`` kiểm tra trực tiếp ``(class, rdf:type, owl:Class)``, nên
một lớp được dùng mà quên khai báo sẽ làm hỏng cả chuỗi kiểm tra chứ không chỉ
thiếu tài liệu. Đây chính là lỗ hổng đã tồn tại khi các miền học phí và chứng chỉ
mới được chuyển sang: 42 quan hệ và 22 lớp dùng mà chưa khai.
"""

import re

import pytest
from rdflib import OWL, RDF, RDFS, SKOS, Literal, URIRef

from ontchatbot.settings import ONTOLOGY_NS

PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
CAMEL_CASE = re.compile(r"^[a-z][A-Za-z0-9]*$")
#: Lớp trừu tượng chỉ dùng làm cha, không có cá thể nào.
ABSTRACT_CLASSES = {"DocumentPart", "OfficialDocument"}


def _local(node) -> str:
    return str(node).rsplit("#", 1)[-1]


def _project(nodes) -> set:
    return {node for node in nodes if str(node).startswith(ONTOLOGY_NS)}


@pytest.fixture(scope="module")
def declared(ontology_graph):
    return {
        "class": {_local(node) for node in _project(ontology_graph.subjects(RDF.type, OWL.Class))},
        "object": {
            _local(node)
            for node in _project(ontology_graph.subjects(RDF.type, OWL.ObjectProperty))
        },
        "datatype": {
            _local(node)
            for node in _project(ontology_graph.subjects(RDF.type, OWL.DatatypeProperty))
        },
    }


def test_every_used_class_is_declared(ontology_graph, declared) -> None:
    used = {
        _local(item)
        for _, item in ontology_graph.subject_objects(RDF.type)
        if str(item).startswith(ONTOLOGY_NS)
    }

    assert used - declared["class"] == set()


def test_every_used_property_is_declared(ontology_graph, declared) -> None:
    used = {_local(item) for item in _project(set(ontology_graph.predicates()))}

    assert used - (declared["object"] | declared["datatype"]) == set()


def test_no_declaration_is_left_unused(ontology_graph, declared) -> None:
    """Khai báo thừa nghĩa là lược đồ đang mô tả thứ dữ liệu không có."""

    used_classes = {
        _local(item)
        for _, item in ontology_graph.subject_objects(RDF.type)
        if str(item).startswith(ONTOLOGY_NS)
    }
    used_properties = {_local(item) for item in _project(set(ontology_graph.predicates()))}

    assert declared["class"] - used_classes - ABSTRACT_CLASSES == set()
    assert declared["object"] | declared["datatype"] <= used_properties | set()


def test_naming_conventions_hold(declared) -> None:
    assert [name for name in declared["class"] if not PASCAL_CASE.match(name)] == []
    properties = declared["object"] | declared["datatype"]
    assert [name for name in properties if not CAMEL_CASE.match(name)] == []


def test_every_declared_term_carries_a_vietnamese_label(ontology_graph, declared) -> None:
    missing = []
    for group in declared.values():
        for name in sorted(group):
            labels = list(ontology_graph.objects(URIRef(ONTOLOGY_NS + name), RDFS.label))
            if not any(getattr(label, "language", None) == "vi" for label in labels):
                missing.append(name)

    assert missing == []


def test_every_named_individual_carries_a_vietnamese_label(ontology_graph) -> None:
    missing = [
        _local(node)
        for node in sorted(_project(ontology_graph.subjects(RDF.type, OWL.NamedIndividual)), key=str)
        if not any(
            getattr(label, "language", None) == "vi"
            for label in ontology_graph.objects(node, RDFS.label)
        )
    ]

    assert missing == []


def test_alternative_labels_are_names_not_questions(ontology_graph) -> None:
    """``skos:altLabel`` chỉ chứa tên gọi tương đương.

    Nhãn lỏng nghĩa sẽ được bộ sinh dataset dùng làm biến thể bề mặt và dạy model
    trả lời sai một cách tự tin.
    """

    suspicious = [
        f"{_local(subject)}: {value}"
        for subject, value in ontology_graph.subject_objects(SKOS.altLabel)
        if re.search(r"\?|\bem\b|\btôi\b|làm sao|thế nào|ở đâu", str(value), re.IGNORECASE)
    ]

    assert suspicious == []


def test_only_one_provenance_relation_survives(ontology_graph, declared) -> None:
    """Nội dung và nguồn tách bạch bằng đúng một quan hệ."""

    assert "basedOn" in declared["object"]
    assert not {"sourceDocument", "sourceProvision"} & (
        declared["object"] | declared["datatype"]
    )


def test_language_tagged_text_never_carries_markdown(ontology_graph) -> None:
    leaked = [
        str(value)[:60]
        for _, value in ontology_graph.subject_objects(URIRef(ONTOLOGY_NS + "officialText"))
        if isinstance(value, Literal) and set(str(value)) & set("#*`|")
    ]

    assert leaked == []
