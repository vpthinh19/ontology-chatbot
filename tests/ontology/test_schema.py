from rdflib import Graph, Literal, OWL, RDF, RDFS
from owlrl import DeductiveClosure, OWLRL_Semantics

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


def test_owl_rl_expansion_and_typed_literals_are_valid(ontology_graph) -> None:
    expanded = Graph()
    for triple in ontology_graph:
        expanded.add(triple)
    DeductiveClosure(OWLRL_Semantics).expand(expanded)
    assert len(expanded) >= len(ontology_graph)

    object_properties = set(ontology_graph.subjects(RDF.type, OWL.ObjectProperty))
    datatype_properties = set(ontology_graph.subjects(RDF.type, OWL.DatatypeProperty))
    assert object_properties.isdisjoint(datatype_properties)
    for literal in {node for node in ontology_graph.all_nodes() if isinstance(node, Literal)}:
        if literal.datatype is not None:
            assert literal.toPython() is not literal, literal


def test_semantic_resources_have_direct_source_paths(ontology_graph, academic) -> None:
    semantic_classes = {
        academic.AcademicPolicy,
        academic.AcademicProcedure,
        academic.TuitionRate,
        academic.DoctoralTuitionDurationRule,
        academic.PaymentFeeRule,
        academic.AcademicPerformanceBand,
        academic.StudyYearBand,
        academic.GraduationClassificationBand,
        academic.ClassSizeRule,
        academic.CertificateConversionRule,
    }
    for class_ in semantic_classes:
        for resource in ontology_graph.subjects(RDF.type, class_):
            assert ontology_graph.value(resource, academic.sourceDocument) is not None
            provision = ontology_graph.value(resource, academic.sourceProvision)
            assert provision is not None
            assert (provision, RDF.type, academic.DocumentPart) in ontology_graph or any(
                (provision, RDF.type, subtype) in ontology_graph
                for subtype in {
                    academic.Article,
                    academic.Clause,
                    academic.Point,
                    academic.Appendix,
                    academic.DocumentTableRow,
                }
            )


def test_unused_document_url_property_is_absent(ontology_graph, academic) -> None:
    assert not list(ontology_graph.triples((academic.documentUrl, None, None)))
