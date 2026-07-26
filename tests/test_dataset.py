from __future__ import annotations

from pathlib import Path

import pytest

from ontchatbot.config import DATASET_PATH
from ontchatbot.dataset import DatasetError, load_dataset, validate_dataset
from ontchatbot.query_engine import load_ontology
from ontchatbot.scripts.migrate_dataset_sparql_v1 import convert_queryplan


def test_converts_direct_datatype_route() -> None:
    assert convert_queryplan(
        "query\nroute individual AcademicLeaveProcedure data content"
    ) == "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"


def test_converts_object_endpoint_to_label() -> None:
    assert convert_queryplan(
        "query\nroute individual AcademicLeaveProcedure object handledBy"
    ) == (
        "SELECT ?answer WHERE { :AcademicLeaveProcedure :handledBy ?node . "
        "?node rdfs:label ?answer . }"
    )


def test_converts_flattened_condition() -> None:
    assert convert_queryplan(
        "query\nroute individual AcademicLeaveProcedure object hasCondition"
    ) == "SELECT ?answer WHERE { :AcademicLeaveProcedure :condition ?answer . }"


def test_converts_removed_condition_regulation_hop_to_parent_edge() -> None:
    assert convert_queryplan(
        "query\nroute individual GraduationReviewProcedure object hasCondition "
        "object basedOnRegulation data documentUrl"
    ) == (
        "SELECT ?answer WHERE { :GraduationReviewProcedure :basedOnRegulation ?node . "
        "?node :documentUrl ?answer . }"
    )


def test_converts_multiple_routes_to_multiple_columns() -> None:
    assert convert_queryplan(
        "query\n"
        "route individual AcademicLeaveProcedure object hasCondition\n"
        "route individual AcademicLeaveProcedure object handledBy"
    ) == (
        "SELECT ?condition ?office WHERE { "
        ":AcademicLeaveProcedure :condition ?condition . "
        ":AcademicLeaveProcedure :handledBy ?officeNode . "
        "?officeNode rdfs:label ?office . }"
    )


@pytest.mark.parametrize("dialogue", ["greeting", "unrelated", "clarify"])
def test_excludes_dialogue_from_core_sparql_dataset(dialogue: str) -> None:
    assert convert_queryplan(dialogue) is None


def test_released_dataset_is_executable() -> None:
    if not DATASET_PATH.is_file():
        pytest.skip("SPARQL dataset has not been generated")
    report = validate_dataset(load_dataset(DATASET_PATH), load_ontology())

    assert report["records"] == 948
    assert report["targets"] == 80
    assert report["split_counts"] == {"train": 636, "validation": 312}
    assert report["empty_result_ids"] == []


def test_validator_rejects_family_leakage() -> None:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"
    rows = [
        {
            "id": "a",
            "family_id": "same",
            "split": "train",
            "register": "formal",
            "input": "bảo lưu như thế nào",
            "target": target,
        },
        {
            "id": "b",
            "family_id": "same",
            "split": "validation",
            "register": "noisy",
            "input": "bảo lưu sao",
            "target": target,
        },
    ]

    with pytest.raises(DatasetError, match="families cross splits"):
        validate_dataset(rows, load_ontology())
