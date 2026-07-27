from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.compare import isomorphic
from rdflib.namespace import OWL, SKOS

from ontchatbot.tools.ontology_v12 import migrate

ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_V11 = ROOT / "resources/ontology/ontology_v11.ttl"
ONTOLOGY_V12 = ROOT / "resources/ontology/ontology_v12.ttl"
NS = Namespace("http://www.ntu.edu.vn/ontology/academic#")
ONTOLOGY_IRI = Namespace("http://www.ntu.edu.vn/ontology/").academic


def load(path: Path) -> Graph:
    return Graph().parse(path, format="turtle")


def test_v12_has_expected_shape() -> None:
    graph = load(ONTOLOGY_V12)

    assert len(graph) == 423
    assert (ONTOLOGY_IRI, OWL.versionInfo, Literal("12")) in graph
    assert len(set(graph.subjects(RDF.type, OWL.NamedIndividual))) == 32
    assert len(set(graph.subjects(RDF.type, OWL.ObjectProperty))) == 6
    assert len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))) == 13


def test_graduation_conditions_are_complete_and_queryable() -> None:
    graph = load(ONTOLOGY_V12)
    conditions = set(graph.objects(NS.GraduationReviewProcedure, NS.condition))

    assert conditions == {
        Literal("Hoàn thành nghĩa vụ đối với Trường", lang="vi"),
        Literal("Không bị truy cứu trách nhiệm hình sự và không bị kỷ luật", lang="vi"),
        Literal("Tích lũy đủ số tín chỉ theo quy định", lang="vi"),
        Literal("Điểm trung bình chung tích lũy (CPA) từ 5.5 trở lên", lang="vi"),
        Literal("Đạt chuẩn năng lực tiếng Anh theo quy định", lang="vi"),
        Literal("Hoàn thành học phần Giáo dục quốc phòng và an ninh", lang="vi"),
        Literal("Hoàn thành học phần Giáo dục thể chất", lang="vi"),
    }


def test_scholarship_condition_and_outcome_do_not_guarantee_an_award() -> None:
    graph = load(ONTOLOGY_V12)

    assert (
        NS.ScholarshipReviewProcedure,
        NS.condition,
        Literal("Không bị kỷ luật từ mức khiển trách trở lên", lang="vi"),
    ) in graph
    assert set(graph.objects(NS.ScholarshipReviewProcedure, NS.outcome)) == {
        Literal(
            "Được đưa vào danh sách xét học bổng; học bổng được cấp theo thứ tự kết quả học tập cho đến khi hết chỉ tiêu",
            lang="vi",
        )
    }


def test_major_change_receiving_and_processing_roles_are_distinct() -> None:
    graph = load(ONTOLOGY_V12)

    assert (NS.receivedBy, RDF.type, OWL.ObjectProperty) in graph
    assert (NS.receivedBy, RDFS.domain, NS.AcademicProcedure) in graph
    assert (NS.receivedBy, RDFS.range, NS.AdministrativeOffice) in graph
    assert set(graph.objects(NS.MajorChangeProcedure, NS.receivedBy)) == {
        NS.StudentAffairsOffice
    }
    assert set(graph.objects(NS.MajorChangeProcedure, NS.handledBy)) == {
        NS.UndergraduateEducationOffice
    }


def test_office_has_canonical_label_and_aliases() -> None:
    graph = load(ONTOLOGY_V12)

    assert set(graph.objects(NS.StudentAffairsOffice, RDFS.label)) == {
        Literal("Phòng Công tác Chính trị và Sinh viên", lang="vi")
    }
    assert {
        Literal("Phòng Công tác Sinh viên", lang="vi"),
        Literal("Phòng CTCTSV", lang="vi"),
        Literal("CTCTSV", lang="vi"),
        Literal("CTSV", lang="vi"),
    } <= set(graph.objects(NS.StudentAffairsOffice, SKOS.altLabel))


def test_all_labels_and_aliases_remain_vietnamese() -> None:
    graph = load(ONTOLOGY_V12)

    for predicate in (RDFS.label, SKOS.altLabel):
        for value in graph.objects(None, predicate):
            assert isinstance(value, Literal)
            assert value.language == "vi"


def test_named_schema_is_complete() -> None:
    graph = load(ONTOLOGY_V12)
    entity_types = (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.NamedIndividual)
    entities = {
        subject
        for entity_type in entity_types
        for subject in graph.subjects(RDF.type, entity_type)
        if isinstance(subject, URIRef)
    }

    assert len(entities) == 57
    assert all(list(graph.objects(entity, RDFS.label)) for entity in entities)

    labels: dict[Literal, list[URIRef]] = {}
    for entity in entities:
        for label in graph.objects(entity, RDFS.label):
            labels.setdefault(label, []).append(entity)
    assert all(len(resources) == 1 for resources in labels.values())

    properties = set(graph.subjects(RDF.type, OWL.ObjectProperty)) | set(
        graph.subjects(RDF.type, OWL.DatatypeProperty)
    )
    assert all(list(graph.objects(prop, RDFS.domain)) for prop in properties)
    assert all(list(graph.objects(prop, RDFS.range)) for prop in properties)

    internal_references = {
        value
        for value in graph.objects()
        if isinstance(value, URIRef) and str(value).startswith(str(NS))
    }
    defined_resources = {subject for subject in graph.subjects() if isinstance(subject, URIRef)}
    assert internal_references <= defined_resources


def test_migration_is_reproducible(tmp_path: Path) -> None:
    target = tmp_path / "ontology_v12.ttl"
    manifest = tmp_path / "ontology_v11_to_v12.json"

    result = migrate(ONTOLOGY_V11, target, manifest)

    assert result["source_triples"] == 410
    assert result["target_triples"] == 423
    assert isomorphic(load(target), load(ONTOLOGY_V12))
    assert manifest.is_file()
