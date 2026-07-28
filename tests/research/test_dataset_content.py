from __future__ import annotations

import re

from rdflib import RDF, Namespace

from ontchatbot.research.catalogue import load_catalogue
from ontchatbot.research.dataset import load_release, validate_release
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import QUERY_CATALOGUE_PATH


ACADEMIC = Namespace("http://www.ntu.edu.vn/ontology/academic#")
PROCEDURE_FAMILIES = {
    "procedure-instruction",
    "procedure-eligibility",
    "procedure-deadline",
    "procedure-result",
    "procedure-submission-office",
    "procedure-review-office",
    "procedure-required-form",
    "procedure-form-download",
    "procedure-overview",
}
SECONDARY_FAMILIES = {
    "tuition-program-cohort-rate",
    "payment-method-list",
    "payment-bank-list",
    "payment-fee",
    "payment-warning",
    "form-list",
    "form-download",
    "academic-performance-band",
    "study-year-band",
    "graduation-classification-band",
    "class-size-rule",
    "language-certificate-level",
    "certificate-criterion",
    "computer-certificate-grade",
}
SOURCE_TYPES = {
    ACADEMIC.Chapter,
    ACADEMIC.Article,
    ACADEMIC.Clause,
    ACADEMIC.Point,
}
LOCAL_NAME = re.compile(r":([A-Za-z][A-Za-z0-9]*)")


def test_official_release_is_executable_and_covers_procedure_families() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    report = validate_release(load_release(), graph, catalogue)

    assert PROCEDURE_FAMILIES <= set(catalogue)
    assert report["domains"]["procedure"] > 0


def test_all_academic_procedures_are_declared_and_seen_in_train() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    report = validate_release(load_release(), graph, catalogue)
    expected = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.AcademicProcedure)
    }
    declared = {
        value
        for spec in catalogue.values()
        if spec.domain == "procedure"
        for slot in spec.slots.values()
        for value in slot.values
    }
    seen = {
        value
        for query_id, slots in report["slot_coverage"].items()
        if catalogue[query_id].domain == "procedure"
        for details in slots.values()
        for value in details["seen_train"]
    }

    assert len(expected) == 20
    assert expected <= declared
    assert expected <= seen


def test_targets_do_not_restore_old_schema_or_query_source_nodes_directly() -> None:
    graph = load_ontology()
    rows = [row for split in load_release().values() for row in split]
    forbidden_properties = (":content", ":condition", ":outcome", ":handledBy", ":receivedBy")

    for row in rows:
        target = row["target"]
        assert not any(name in target for name in forbidden_properties)
        for local_name in LOCAL_NAME.findall(target):
            resource = ACADEMIC[local_name]
            assert not any((resource, RDF.type, source_type) in graph for source_type in SOURCE_TYPES)


def test_secondary_query_families_cover_finite_ontology_values() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    report = validate_release(load_release(), graph, catalogue)

    assert SECONDARY_FAMILIES <= set(catalogue)

    expected_programs = {
        f":{str(program).rsplit('#', 1)[-1]}"
        for rate in graph.subjects(RDF.type, ACADEMIC.TuitionRate)
        for program in graph.objects(rate, ACADEMIC.appliesToProgram)
    }
    expected_language_certificates = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.LanguageCertificate)
    }
    expected_computer_certificates = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.ComputerCertificate)
    }
    # Class-size rows are represented directly as rules; the ontology does not
    # attach synthetic CourseCategory nodes to these official table rows.
    expected_class_size_rules = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.ClassSizeRule)
    }

    assert len(expected_programs) == 29
    assert len(expected_language_certificates) == 15
    assert len(expected_computer_certificates) == 3
    assert len(expected_class_size_rules) == 14
    assert expected_programs <= set(
        catalogue["tuition-program-cohort-rate"].slots["program"].values
    )
    assert expected_language_certificates <= set(
        catalogue["certificate-criterion"].slots["certificate"].values
    )
    assert expected_computer_certificates <= set(
        catalogue["computer-certificate-grade"].slots["certificate"].values
    )
    assert expected_class_size_rules <= set(
        catalogue["class-size-rule"].slots["rule"].values
    )

    for query_id in SECONDARY_FAMILIES:
        for details in report["slot_coverage"][query_id].values():
            assert details["missing_train"] == []
