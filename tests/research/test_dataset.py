from __future__ import annotations

import pytest

from ontchatbot.research.dataset import (
    DatasetError,
    load_release,
    validate_dataset,
    validate_release,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import DATASET_DIR


def test_canonical_dataset_is_executable() -> None:
    if not DATASET_DIR.is_dir():
        pytest.skip("SPARQL dataset has not been generated")
    report = validate_release(load_release(), load_ontology())

    assert report["records"] == 1416
    assert report["split_counts"] == {"train": 1084, "val": 164, "test": 168}
    assert all(not split["empty_result_ids"] for split in report["splits"].values())


def test_validator_rejects_family_leakage() -> None:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"

    def family(prefix: str, family_id: str, question: str) -> list[dict[str, str]]:
        return [
            {
                "id": f"{prefix}-{index}",
                "family_id": family_id,
                "register": register,
                "input": f"{question} {register}",
                "target": target,
            }
            for index, register in enumerate(
                ("formal", "neutral", "colloquial", "noisy"),
                1,
            )
        ]

    release = {
        "train": family("a", "same", "bảo lưu như thế nào"),
        "val": family("b", "same", "bảo lưu sao"),
        "test": family("c", "independent", "xin hướng dẫn bảo lưu"),
    }

    with pytest.raises(DatasetError, match="families cross splits"):
        validate_release(release, load_ontology())


def test_validator_rejects_removed_query_shape_field() -> None:
    row = {
        "id": "question-1",
        "family_id": "family-1",
        "register": "formal",
        "query_shape": "direct",
        "input": "bảo lưu như thế nào",
        "target": "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }",
    }

    with pytest.raises(DatasetError, match="fields must be exactly"):
        validate_release(
            {
                "train": [row],
                "val": [
                    {
                        **row,
                        "id": "question-2",
                        "family_id": "family-2",
                        "input": "bảo lưu ra sao",
                    }
                ],
                "test": [
                    {
                        **row,
                        "id": "question-3",
                        "family_id": "family-3",
                        "input": "xin hướng dẫn bảo lưu",
                    }
                ],
            },
            load_ontology(),
        )


def test_validator_rejects_family_missing_a_register() -> None:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"
    rows = [
        {
            "id": f"question-{index}",
            "family_id": "family-1",
            "register": register,
            "input": f"hỏi về bảo lưu {register}",
            "target": target,
        }
        for index, register in enumerate(("formal", "neutral", "colloquial"), 1)
    ]

    with pytest.raises(DatasetError, match="exactly one of each register"):
        validate_dataset(rows, load_ontology())


def test_validator_rejects_near_duplicate_questions_across_splits() -> None:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"

    def family(prefix: str, family_id: str, question: str) -> list[dict[str, str]]:
        return [
            {
                "id": f"{prefix}-{index}",
                "family_id": family_id,
                "register": register,
                "input": f"{question} cách {index}",
                "target": target,
            }
            for index, register in enumerate(
                ("formal", "neutral", "colloquial", "noisy"),
                1,
            )
        ]

    release = {
        "train": family(
            "train",
            "family-train",
            "Liệt kê hai mức học phí mỗi tín chỉ khác nhau cao nhất của khóa K66",
        ),
        "val": family("val", "family-val", "Hướng dẫn bảo lưu kết quả học tập"),
        "test": family(
            "test",
            "family-test",
            "Liệt kê hai mức học phí mỗi tín chỉ khác nhau cao nhất của khóa K65",
        ),
    }

    with pytest.raises(DatasetError, match="near-duplicate questions cross splits"):
        validate_release(release, load_ontology())
