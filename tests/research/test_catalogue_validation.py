from __future__ import annotations

import pytest

from ontchatbot.research.catalogue import CoverageSelector, QuerySpec, SlotSpec
from ontchatbot.research.catalogue_validation import (
    CatalogueValidationError,
    validate_catalogue,
)
from ontchatbot.runtime.sparql import load_ontology


INVENTORY = {
    "schema_version": 1,
    "entries": [
        {
            "id": "TemporaryAcademicLeaveProcedure-instructionProvision-officialText",
            "anchor": "TemporaryAcademicLeaveProcedure",
            "answer_kind": "literal",
            "path": ["instructionProvision", "officialText"],
            "provenance": ["Decision1052Article15"],
            "status": "supported",
        },
        {
            "id": "TemporaryAcademicLeaveProcedure-submittedTo-rdfs-label",
            "anchor": "TemporaryAcademicLeaveProcedure",
            "answer_kind": "label",
            "path": ["submittedTo", "rdfs:label"],
            "provenance": ["Decision1052Article15"],
            "status": "supported",
        },
    ],
}


def _spec(
    query_id: str,
    path: tuple[str, ...],
    *,
    anchor_classes: tuple[str, ...] = ("AcademicProcedure",),
    anchors: tuple[str, ...] = ("TemporaryAcademicLeaveProcedure",),
    slot_values: tuple[str, ...] = (":TemporaryAcademicLeaveProcedure",),
) -> QuerySpec:
    predicate = path[0]
    tail = (
        f"?node :{path[1]} ?answer ."
        if len(path) == 2 and path[1] != "rdfs:label"
        else "?node rdfs:label ?answer ."
    )
    return QuerySpec(
        query_id,
        "procedure",
        f"SELECT ?answer WHERE {{ ${{procedure}} :{predicate} ?node . {tail} }}",
        {"procedure": SlotSpec("iri", slot_values)},
        (CoverageSelector(anchor_classes, (path,), anchors),),
    )


def _complete_catalogue() -> dict[str, QuerySpec]:
    return {
        "procedure-instruction": _spec(
            "procedure-instruction",
            ("instructionProvision", "officialText"),
        ),
        "procedure-submission": _spec(
            "procedure-submission",
            ("submittedTo", "rdfs:label"),
        ),
    }


def test_valid_catalogue_covers_every_supported_entry() -> None:
    report = validate_catalogue(load_ontology(), INVENTORY, _complete_catalogue())

    assert report["supported_entries"] == 2
    assert report["covered_entries"] == 2
    assert report["uncovered_entries"] == []
    assert report["families"] == 2


def test_rejects_uncovered_supported_entry() -> None:
    catalogue = _complete_catalogue()
    catalogue.pop("procedure-submission")

    with pytest.raises(CatalogueValidationError, match="uncovered supported"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_rejects_selector_that_matches_no_supported_entry() -> None:
    catalogue = _complete_catalogue()
    catalogue["unused"] = _spec("unused", ("webPageUrl",))

    with pytest.raises(CatalogueValidationError, match="matches no supported entry"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_rejects_selector_anchor_with_wrong_class() -> None:
    catalogue = _complete_catalogue()
    catalogue["procedure-instruction"] = _spec(
        "procedure-instruction",
        ("instructionProvision", "officialText"),
        anchor_classes=("Certificate",),
    )

    with pytest.raises(CatalogueValidationError, match="does not belong to"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


@pytest.mark.parametrize(
    ("slot_value", "message"),
    [
        (":StandardEnglishCertificateTableRule03IELTS", "opaque record"),
        (":ResourceThatDoesNotExist", "does not exist"),
    ],
)
def test_rejects_invalid_model_facing_iri_slots(slot_value, message) -> None:
    catalogue = _complete_catalogue()
    catalogue["procedure-instruction"] = _spec(
        "procedure-instruction",
        ("instructionProvision", "officialText"),
        slot_values=(slot_value,),
    )

    with pytest.raises(CatalogueValidationError, match=message):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)


def test_rejects_non_rejection_spec_without_coverage() -> None:
    catalogue = _complete_catalogue()
    catalogue["procedure-instruction"] = QuerySpec(
        "procedure-instruction",
        "procedure",
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure rdfs:label ?answer . }",
        {},
    )

    with pytest.raises(CatalogueValidationError, match="declares no coverage"):
        validate_catalogue(load_ontology(), INVENTORY, catalogue)
