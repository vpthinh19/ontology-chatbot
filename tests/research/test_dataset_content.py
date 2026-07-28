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
