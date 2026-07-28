from __future__ import annotations

import json

import pytest

from ontchatbot.research.catalogue import CatalogueError, load_catalogue, match_target


PROCEDURE = {
    "query_id": "procedure-instruction",
    "domain": "procedure",
    "target_template": (
        "SELECT ?answer WHERE { ${procedure} :instructionProvision ?part . "
        "?part :officialText ?answer . }"
    ),
    "slots": {
        "procedure": {
            "kind": "iri",
            "values": [
                ":CourseRegistrationProcedure",
                ":CourseRetakeProcedure",
            ],
        }
    },
}
PERFORMANCE = {
    "query_id": "performance-band",
    "domain": "academic-rule",
    "target_template": (
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; "
        ":minimumValue ?minimum ; :maximumValue ?maximum ; "
        ":resultLabel ?answer . FILTER (?minimum <= ${score} && "
        "${score} <= ?maximum) }"
    ),
    "slots": {"score": {"kind": "number"}},
}
REJECTION = {
    "query_id": "no-information",
    "domain": "out-of-domain",
    "target_template": "không có thông tin",
    "slots": {},
}


def _write_catalogue(tmp_path, records):
    path = tmp_path / "catalogue.jsonl"
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )
    return path


def test_loads_catalogue_and_matches_static_iri_and_number_targets(tmp_path) -> None:
    catalogue = load_catalogue(
        _write_catalogue(tmp_path, [PROCEDURE, PERFORMANCE, REJECTION])
    )

    assert list(catalogue) == [
        "procedure-instruction",
        "performance-band",
        "no-information",
    ]
    assert match_target(
        catalogue["procedure-instruction"],
        "SELECT ?answer WHERE { :CourseRetakeProcedure :instructionProvision ?part . "
        "?part :officialText ?answer . }",
    ) == {"procedure": ":CourseRetakeProcedure"}
    assert match_target(
        catalogue["performance-band"],
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; "
        ":minimumValue ?minimum ; :maximumValue ?maximum ; "
        ":resultLabel ?answer . FILTER (?minimum <= 8.5 && 8.5 <= ?maximum) }",
    ) == {"score": "8.5"}
    assert match_target(catalogue["no-information"], "không có thông tin") == {}


def test_target_must_use_declared_iri_and_same_repeated_number(tmp_path) -> None:
    catalogue = load_catalogue(_write_catalogue(tmp_path, [PROCEDURE, PERFORMANCE]))

    assert match_target(
        catalogue["procedure-instruction"],
        "SELECT ?answer WHERE { :UnknownProcedure :instructionProvision ?part . "
        "?part :officialText ?answer . }",
    ) is None
    assert match_target(
        catalogue["performance-band"],
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; "
        ":minimumValue ?minimum ; :maximumValue ?maximum ; "
        ":resultLabel ?answer . FILTER (?minimum <= 8.5 && 9 <= ?maximum) }",
    ) is None


def test_rejects_duplicate_query_id(tmp_path) -> None:
    with pytest.raises(CatalogueError, match="duplicate query_id"):
        load_catalogue(_write_catalogue(tmp_path, [REJECTION, REJECTION]))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"domain": "unknown"}, "invalid domain"),
        ({"target_template": "SELECT ${missing} WHERE { }"}, "undeclared slots"),
        (
            {
                "slots": {
                    **PROCEDURE["slots"],
                    "unused": {"kind": "number"},
                }
            },
            "unused slots",
        ),
        (
            {
                "slots": {
                    "procedure": {
                        "kind": "iri",
                        "values": ["CourseRegistrationProcedure"],
                    }
                }
            },
            "invalid IRI slot value",
        ),
    ],
)
def test_rejects_malformed_catalogue_records(tmp_path, change, message) -> None:
    record = {**PROCEDURE, **change}

    with pytest.raises(CatalogueError, match=message):
        load_catalogue(_write_catalogue(tmp_path, [record]))
