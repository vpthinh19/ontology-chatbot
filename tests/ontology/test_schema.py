from rdflib import OWL, RDF, RDFS

from ontchatbot.settings import ONTOLOGY_NS


SOURCE_CLASSES = {
    "DocumentComponent",
    "OfficialDocument",
    "Decision",
    "GuidanceDocument",
    "DocumentPart",
    "AttachedRegulation",
    "Chapter",
    "Article",
    "Clause",
    "Point",
    "Appendix",
    "DocumentTable",
    "DocumentTableRow",
}

FORBIDDEN_LOCAL_NAMES = {
    "Condition",
    "Outcome",
    "content",
    "hasCondition",
    "hasOutcome",
    "CourseWithdrawalProcedure",
    "ScholarshipReviewProcedure",
    "TuitionPaymentExtensionForm",
}


def test_official_source_schema_exists(ontology_graph, academic) -> None:
    classes = set(ontology_graph.subjects(RDF.type, OWL.Class))
    assert {academic[name] for name in SOURCE_CLASSES} <= classes
    assert (academic.hasPart, OWL.inverseOf, academic.partOf) in ontology_graph


def test_schema_avoids_union_domains_and_removed_vocabulary(
    ontology_graph, academic
) -> None:
    assert not list(ontology_graph.triples((None, OWL.unionOf, None)))
    for local_name in FORBIDDEN_LOCAL_NAMES:
        resource = academic[local_name]
        assert not list(ontology_graph.triples((resource, None, None)))
        assert not list(ontology_graph.triples((None, None, resource)))


def test_every_named_project_resource_has_vietnamese_label(ontology_graph) -> None:
    named_types = {
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.NamedIndividual,
    }
    resources = {
        subject
        for rdf_type in named_types
        for subject in ontology_graph.subjects(RDF.type, rdf_type)
        if str(subject).startswith(ONTOLOGY_NS)
    }
    assert resources
    for resource in resources:
        labels = list(ontology_graph.objects(resource, RDFS.label))
        assert any(label.language == "vi" for label in labels), resource
