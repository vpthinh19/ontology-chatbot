from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL, SKOS

ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY_V10 = ROOT / "resources/ontology/ontology_v10.ttl"
ONTOLOGY_V11 = ROOT / "resources/ontology/ontology_v11.ttl"
NS = Namespace("http://www.ntu.edu.vn/ontology/academic#")
ONTOLOGY_IRI = URIRef("http://www.ntu.edu.vn/ontology/academic")


def load(path: Path) -> Graph:
    return Graph().parse(path, format="turtle")


def test_v11_has_expected_shape() -> None:
    graph = load(ONTOLOGY_V11)

    assert len(graph) == 410
    assert (ONTOLOGY_IRI, OWL.versionInfo, Literal("11")) in graph
    assert len(set(graph.subjects(RDF.type, OWL.NamedIndividual))) == 32
    assert len(set(graph.subjects(RDF.type, OWL.ObjectProperty))) == 5
    assert len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))) == 13


def test_condition_and_outcome_values_are_preserved_exactly() -> None:
    old = load(ONTOLOGY_V10)
    new = load(ONTOLOGY_V11)

    for old_property, new_property in (
        (NS.hasCondition, NS.condition),
        (NS.hasOutcome, NS.outcome),
    ):
        expected = {
            (parent, label)
            for parent, wrapper in old.subject_objects(old_property)
            for label in old.objects(wrapper, RDFS.label)
        }
        actual = set(new.subject_objects(new_property))
        assert actual == expected


def test_retired_wrapper_schema_and_resources_are_absent() -> None:
    old = load(ONTOLOGY_V10)
    new = load(ONTOLOGY_V11)

    retired = {NS.Condition, NS.Outcome, NS.hasCondition, NS.hasOutcome}
    retired.update(old.objects(None, NS.hasCondition))
    retired.update(old.objects(None, NS.hasOutcome))

    for resource in retired:
        assert not list(new.triples((resource, None, None)))
        assert not list(new.triples((None, None, resource)))


def test_content_and_graph_connectors_are_preserved() -> None:
    old = load(ONTOLOGY_V10)
    new = load(ONTOLOGY_V11)
    retired_wrappers = set(old.objects(None, NS.hasCondition)) | set(old.objects(None, NS.hasOutcome))

    assert set(old.subject_objects(NS.content)) == set(new.subject_objects(NS.content))
    for predicate in (
        NS.handledBy,
        NS.hasDocument,
        NS.basedOnRegulation,
        NS.supportsPaymentMethod,
        NS.appliesTuitionRate,
    ):
        expected = {
            (subject, value)
            for subject, value in old.subject_objects(predicate)
            if subject not in retired_wrappers
        }
        assert expected == set(new.subject_objects(predicate))
        assert (predicate, RDF.type, OWL.ObjectProperty) in new


def test_labels_and_aliases_follow_language_contract() -> None:
    graph = load(ONTOLOGY_V11)

    for predicate in (RDFS.label, SKOS.altLabel):
        for value in graph.objects(None, predicate):
            assert isinstance(value, Literal)
            assert value.language == "vi"

    removed_aliases = {
        (NS.AcademicLeaveProcedure, Literal("điều kiện bảo lưu", lang="vi")),
        (NS.appliesTuitionRate, Literal("học phí", lang="vi")),
        (NS.documentUrl, Literal("tải biểu mẫu", lang="vi")),
        (NS.handledBy, Literal("xử lý", lang="vi")),
        (NS.hasDocument, Literal("đơn", lang="vi")),
        (NS.headName, Literal("phụ trách", lang="vi")),
        (NS.location, Literal("ở đâu", lang="vi")),
    }
    assert all((resource, SKOS.altLabel, value) not in graph for resource, value in removed_aliases)


def test_reference_sparql_queries_return_user_values() -> None:
    graph = load(ONTOLOGY_V11)
    prefixes = """
        PREFIX : <http://www.ntu.edu.vn/ontology/academic#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    """
    queries = (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }",
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :condition ?answer . }",
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :outcome ?answer . }",
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?office . ?office rdfs:label ?answer . }",
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?office . ?office :email ?answer . }",
        "SELECT ?document ?url WHERE { :AcademicLeaveProcedure :hasDocument ?node . ?node rdfs:label ?document ; :documentUrl ?url . }",
        "SELECT (COUNT(DISTINCT ?method) AS ?answer) WHERE { :TuitionPaymentProcedure :supportsPaymentMethod ?method . }",
    )

    for query in queries:
        rows = list(graph.query(prefixes + query))
        assert rows
        assert all(not isinstance(value, URIRef) for row in rows for value in row if value is not None)
