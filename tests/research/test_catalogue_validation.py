from __future__ import annotations

import json
from itertools import product

import pytest

from ontchatbot.catalogue import (
    CoverageSelector,
    QuerySpec,
    SlotSpec,
    load_catalogue,
)
from ontchatbot.research.catalogue_validation import (
    CatalogueValidationError,
    validate_catalogue,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.runtime.sparql import execute_select
from ontchatbot.settings import ANSWER_INVENTORY_PATH, QUERY_CATALOGUE_PATH


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


def test_canonical_catalogue_covers_supported_inventory() -> None:
    graph = load_ontology()
    inventory = json.loads(ANSWER_INVENTORY_PATH.read_text(encoding="utf-8"))
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    report = validate_catalogue(graph, inventory, catalogue)

    assert report["supported_entries"] == report["covered_entries"]
    assert report["uncovered_entries"] == []


def test_static_and_finite_iri_catalogue_queries_return_literals() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)

    for query_id, spec in catalogue.items():
        if spec.domain == "out-of-domain" or any(
            slot.kind == "number" for slot in spec.slots.values()
        ):
            continue
        names = list(spec.slots)
        combinations = product(*(spec.slots[name].values for name in names))
        for values in combinations:
            query = spec.target_template
            for name, value in zip(names, values, strict=True):
                query = query.replace(f"${{{name}}}", value)
            assert execute_select(graph, query, max_rows=500), (query_id, values)


@pytest.mark.parametrize(
    "amount",
    ["460000", "505000", "510000", "550000", "600000", "620000", "24500000"],
)
def test_tuition_programs_by_rate_returns_programs_for_every_declared_amount(amount: str) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    spec = catalogue["tuition-programs-by-rate"]
    target = spec.target_template.replace("${amount}", amount)

    assert execute_select(load_ontology(), target), amount


@pytest.mark.parametrize(
    ("certificate", "score", "expected"),
    [
        (":TCFCertificate", "100", []),
        (":TCFCertificate", "200", [{"answer": "Bậc 1 - A1"}]),
        (":KLPTCertificate", "300", [{"answer": "Bậc 2 - A2"}]),
        (":KLPTCertificate", "400", [{"answer": "Bậc 4 - B2"}]),
        (":KLPTCertificate", "450", [{"answer": "Bậc 5 - C1"}]),
    ],
)
def test_language_certificate_level_respects_exclusive_minimums(
    certificate: str,
    score: str,
    expected: list[dict[str, str]],
) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    target = catalogue["language-certificate-level"].target_template
    target = target.replace("${certificate}", certificate).replace("${score}", score)

    assert execute_select(load_ontology(), target) == expected


@pytest.mark.parametrize(
    ("credits", "expected"),
    [
        ("35", [{"answer": "Sinh viên năm thứ hai"}]),
        ("70", [{"answer": "Sinh viên năm thứ ba"}]),
        ("105", []),
        ("105.1", [{"answer": "Sinh viên năm thứ tư"}]),
    ],
)
def test_study_year_band_respects_inclusive_boundaries(
    credits: str,
    expected: list[dict[str, str]],
) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    target = catalogue["study-year-band"].target_template.replace("${credits}", credits)

    assert execute_select(load_ontology(), target) == expected


def test_study_year_bands_remain_reachable_by_credit_count() -> None:
    """Bảng xếp hạng năm đào tạo bị họ ``*-details`` cũ bỏ lại phía sau.

    Họ đó dựng câu trả lời từ ``sourceDocument`` nên không còn chỗ trong lược đồ
    mới; điều cần giữ là bốn mốc tín chỉ vẫn tra được.
    """

    graph = load_ontology()
    rows = execute_select(
        graph,
        "SELECT ?answer WHERE { ?band a :StudyYearBand ; :resultLabel ?answer . }",
    )

    assert len(rows) == 4
