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


def test_runtime_source_projection_is_not_answerable(answer_inventory) -> None:
    """Runtime-only source fields must not become hand-authored answer paths."""

    derived_fields = {"sourceCitation", "sourceLink"}

    assert all(
        not derived_fields.intersection(entry["path"])
        for entry in answer_inventory["entries"]
    )


def test_known_semantic_decisions_are_in_inventory(answer_inventory) -> None:
    entries = {
        item["id"]: item
        for item in answer_inventory["entries"]
    }

    assert entries[
        "AcademicDismissalPolicy-basedOn-officialText"
    ]["status"] == "supported"
    assert entries[
        "SickLeaveProcedure-hasStep-stepText"
    ]["status"] == "supported"
    assert entries[
        "ArticulationStudyProcedure-requiresForm"
    ]["status"] == "excluded"
    assert entries["ArticulationStudyProcedure-requiresForm"]["reason"]


def test_opaque_record_labels_are_not_supported(answer_inventory) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}

    assert entries["VNPAYOtherBankFee-rdfs-label"]["status"] == "excluded"
    assert entries[
        "TemporaryAcademicLeaveProcedure-rdfs-label"
    ]["status"] == "supported"


def test_business_values_inside_opaque_records_remain_supported(
    answer_inventory,
) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}

    assert entries["VNPAYOtherBankFee-feeAmount"]["status"] == "supported"
    assert entries[
        "Regulation1052Appendix2Table03-verbatimTableText"
    ]["status"] == "supported"
    assert entries[
        "Regulation1052Appendix2Table03-officialText"
    ]["status"] == "excluded"


@pytest.mark.parametrize(
    "entry_id",
    [
        "CourseWithdrawalProcedure-requiresForm-rdfs-label",
        "Regulation1052Appendix2Table03-partOf-rdfs-label",
        "DirectBankingFreeFee-appliesToPaymentMethod-rdfs-label",
        "ExcellentSpecialScholarshipRate-billingUnit-rdfs-label",
        "FormCatalogueEntry001-catalogueEntryForForm-rdfs-label",
        "UndergraduateFormCatalogue-hasCatalogueEntry-listedTitle",
        "TemporaryAcademicLeaveProcedure-basedOn-citationLabel",
    ],
)
def test_user_facing_object_relations_are_in_inventory(
    answer_inventory,
    entry_id,
) -> None:
    entries = {entry["id"]: entry for entry in answer_inventory["entries"]}

    assert entries[entry_id]["status"] == "supported"
