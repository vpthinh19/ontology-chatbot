from __future__ import annotations

import pytest

from ontchatbot.research.dataset import (
    DatasetError,
    load_release,
    validate_release,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import DATASET_DIR


def test_released_dataset_is_executable() -> None:
    if not DATASET_DIR.is_dir():
        pytest.skip("SPARQL dataset has not been generated")
    report = validate_release(load_release(), load_ontology())

    assert report["records"] == 1112
    assert report["split_counts"] == {"train": 636, "val": 312, "test": 164}
    assert all(not split["empty_result_ids"] for split in report["splits"].values())


def test_validator_rejects_family_leakage() -> None:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"

    def row(record_id: str, family_id: str, question: str) -> dict[str, str]:
        return {
            "id": record_id,
            "family_id": family_id,
            "register": "formal",
            "query_shape": "direct",
            "input": question,
            "target": target,
        }

    release = {
        "train": [row("a", "same", "bảo lưu như thế nào")],
        "val": [row("b", "same", "bảo lưu sao")],
        "test": [row("c", "independent", "xin hướng dẫn bảo lưu")],
    }

    with pytest.raises(DatasetError, match="families cross splits"):
        validate_release(release, load_ontology())
