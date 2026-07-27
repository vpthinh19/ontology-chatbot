from rdflib import OWL, RDF, RDFS

from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ONTOLOGY_NS


def test_canonical_ontology_schema_and_vietnamese_labels() -> None:
    graph = load_ontology()

    assert len(set(graph.subjects(RDF.type, OWL.Class))) == 9
    assert len(set(graph.subjects(RDF.type, OWL.ObjectProperty))) == 6
    assert len(set(graph.subjects(RDF.type, OWL.DatatypeProperty))) == 13
    assert len(set(graph.subjects(RDF.type, OWL.NamedIndividual))) == 32

    resources = set().union(
        graph.subjects(RDF.type, OWL.Class),
        graph.subjects(RDF.type, OWL.ObjectProperty),
        graph.subjects(RDF.type, OWL.DatatypeProperty),
        graph.subjects(RDF.type, OWL.NamedIndividual),
    )
    for resource in resources:
        if str(resource).startswith(ONTOLOGY_NS):
            assert any(label.language == "vi" for label in graph.objects(resource, RDFS.label))


def test_conditions_and_outcomes_are_literals_not_wrapper_nodes() -> None:
    graph = load_ontology()
    local_names = {str(subject).removeprefix(ONTOLOGY_NS) for subject in graph.subjects()}

    assert "Condition" not in local_names
    assert "Outcome" not in local_names
    assert "hasCondition" not in local_names
    assert "hasOutcome" not in local_names
