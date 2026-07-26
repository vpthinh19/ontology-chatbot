from __future__ import annotations

import pytest

from ontchatbot.config import DATASET_PATH
from ontchatbot.dataset import DatasetError, load_dataset, validate_dataset
from ontchatbot.query_engine import load_ontology


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
