import json

import pytest
from rdflib import Literal, URIRef

from ontchatbot.research.inventory import build_answer_inventory, resolve_answer_path
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ANSWER_INVENTORY_PATH, ONTOLOGY_NS


@pytest.fixture(scope="module")
def ontology_graph():
    return load_ontology()


@pytest.fixture(scope="module")
def answer_inventory(ontology_graph):
    return build_answer_inventory(ontology_graph)


def test_committed_inventory_matches_canonical_graph(answer_inventory) -> None:
    committed = json.loads(ANSWER_INVENTORY_PATH.read_text(encoding="utf-8"))

    assert committed == answer_inventory


def test_supported_inventory_paths_end_in_literals(
    ontology_graph, answer_inventory
) -> None:
    entries = answer_inventory["entries"]
    graph_nodes = set(ontology_graph.all_nodes())

    assert entries
    assert len({entry["id"] for entry in entries}) == len(entries)
    for entry in entries:
        assert entry["status"] in {"supported", "excluded"}
        assert URIRef(ONTOLOGY_NS + entry["anchor"]) in graph_nodes
        if entry["status"] == "excluded":
            assert entry["reason"]
            continue
        assert entry["answer_kind"] in {"label", "literal", "aggregate"}
        assert entry["path"]
        assert entry["provenance"]
        values = resolve_answer_path(
            ontology_graph,
            entry["anchor"],
            entry["path"],
        )
        assert values
        assert all(isinstance(value, Literal) for value in values)
        for local_name in entry["provenance"]:
            assert URIRef(ONTOLOGY_NS + local_name) in graph_nodes
        if entry["answer_kind"] == "aggregate":
            assert entry["operation"]


def test_known_semantic_decisions_are_in_inventory(answer_inventory) -> None:
    entries = {
        item["id"]: item
        for item in answer_inventory["entries"]
    }

    assert entries[
        "AcademicDismissalPolicy-sourceProvision-officialText"
    ]["status"] == "supported"
    assert entries[
        "SickLeaveProcedure-instructionProvision-officialText"
    ]["status"] == "supported"
    assert entries[
        "ClassAbsenceRequestProcedure-resultProvision"
    ]["status"] == "excluded"


def test_opaque_record_labels_are_not_supported(answer_inventory) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}

    assert entries[
        "StandardEnglishCertificateTableRule03IELTS-rdfs-label"
    ]["status"] == "excluded"
    assert entries[
        "Cohort65InformationTechnologyAccreditedRate-rdfs-label"
    ]["status"] == "excluded"
    assert entries[
        "TemporaryAcademicLeaveProcedure-rdfs-label"
    ]["status"] == "supported"


def test_business_values_inside_opaque_records_remain_supported(
    answer_inventory,
) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}

    assert entries[
        "StandardEnglishCertificateTableRule03IELTS-criterionText"
    ]["status"] == "supported"
    assert entries[
        "Cohort65InformationTechnologyAccreditedRate-amount"
    ]["status"] == "supported"


@pytest.mark.parametrize(
    "entry_id",
    [
        "GroupIIIMasterRate-appliesToDisciplineGroup-rdfs-label",
        "DoctoralBachelorEntryFourYearRule-appliesToEntryQualification-rdfs-label",
        "StandardEnglishCertificateTableRule03IELTS-appliesToLearnerCategory-rdfs-label",
        "DirectBankingFreeFee-appliesToPaymentMethod-rdfs-label",
        "AccreditedGeneralEducationRate-billingUnit-rdfs-label",
        "FormCatalogueEntry001-catalogueEntryForForm-rdfs-label",
        "UndergraduateFormCatalogue-hasCatalogueEntry-rdfs-label",
        "TemporaryAcademicLeaveProcedure-sourceDocument-rdfs-label",
    ],
)
def test_user_facing_object_relations_are_in_inventory(
    answer_inventory,
    entry_id,
) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}

    assert entries[entry_id]["status"] == "supported"
