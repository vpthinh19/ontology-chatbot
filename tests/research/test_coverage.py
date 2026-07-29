from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from ontchatbot.research.catalogue import QuerySpec, SlotSpec
from ontchatbot.research.coverage import (
    CoverageError,
    NumericCase,
    assess_coverage,
    load_coverage_requirements,
    require_complete_coverage,
)


VALID_REQUIREMENTS = {
    "priority_domains": ["procedure"],
    "numeric_cases": [
        {
            "query_id": "academic-performance-band",
            "split": "train",
            "slots": {"score": "4.00"},
        }
    ],
    "rejection_classes": [
        "greeting-social",
        "unrelated",
        "near-domain-missing",
        "ambiguous",
        "noisy-out-of-domain",
        "mixed",
        "hard-negative",
    ],
    "required_registers": ["formal", "neutral", "colloquial", "noisy"],
}


def _catalogue() -> dict[str, QuerySpec]:
    return {
        "procedure-family": QuerySpec(
            "procedure-family",
            "procedure",
            "PROCEDURE ${procedure}",
            {"procedure": SlotSpec("iri", (":Procedure",))},
        ),
        "academic-performance-band": QuerySpec(
            "academic-performance-band",
            "academic-rule",
            "SCORE ${score}",
            {"score": SlotSpec("number")},
        ),
        "no-information": QuerySpec(
            "no-information",
            "out-of-domain",
            "không có thông tin",
            {},
        ),
    }


def _write_requirements(tmp_path, payload: object):
    path = tmp_path / "coverage.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loads_immutable_coverage_requirements(tmp_path) -> None:
    requirements = load_coverage_requirements(
        _write_requirements(tmp_path, VALID_REQUIREMENTS),
        {"academic-performance-band": _catalogue()["academic-performance-band"]},
    )

    assert requirements.priority_domains == ("procedure",)
    assert requirements.numeric_cases == (
        NumericCase("academic-performance-band", "train", (("score", "4.00"),)),
    )
    assert requirements.rejection_classes == tuple(VALID_REQUIREMENTS["rejection_classes"])
    assert requirements.required_registers == ("formal", "neutral", "colloquial", "noisy")
    with pytest.raises(FrozenInstanceError):
        requirements.priority_domains += ("tuition",)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"numeric_cases": [{"query_id": "unknown", "split": "train", "slots": {"score": "4.00"}}]}, "unknown query_id"),
        ({"numeric_cases": [{"query_id": "procedure-family", "split": "train", "slots": {"procedure": "4.00"}}]}, "non-number slot"),
        ({"numeric_cases": [{"query_id": "academic-performance-band", "split": "draft", "slots": {"score": "4.00"}}]}, "invalid split"),
        ({"numeric_cases": VALID_REQUIREMENTS["numeric_cases"] * 2}, "duplicate numeric case"),
        ({"rejection_classes": ["greeting-social", "greeting-social"]}, "duplicate rejection class"),
        ({"required_registers": ["formal", "formal"]}, "duplicate required register"),
    ],
)
def test_rejects_invalid_coverage_requirements(tmp_path, change, message) -> None:
    payload = {**VALID_REQUIREMENTS, **change}

    with pytest.raises(CoverageError, match=message):
        load_coverage_requirements(
            _write_requirements(tmp_path, payload),
            _catalogue(),
        )


def test_rejects_missing_coverage_requirement_field(tmp_path) -> None:
    payload = {key: value for key, value in VALID_REQUIREMENTS.items() if key != "priority_domains"}

    with pytest.raises(CoverageError, match="fields must be exactly"):
        load_coverage_requirements(
            _write_requirements(tmp_path, payload),
            {"academic-performance-band": _catalogue()["academic-performance-band"]},
        )


def _complete_splits() -> tuple[dict[str, list[dict[str, str]]], dict[str, list[str]]]:
    splits = {split: [] for split in ("train", "val", "test")}
    checklist: dict[str, list[str]] = {}
    for split, rows in splits.items():
        for register in VALID_REQUIREMENTS["required_registers"]:
            rows.extend(
                [
                    {
                        "id": f"procedure-{split}-{register}",
                        "query_id": "procedure-family",
                        "register": register,
                        "target": "PROCEDURE :Procedure",
                    },
                    {
                        "id": f"performance-{split}-{register}",
                        "query_id": "academic-performance-band",
                        "register": register,
                        "target": "SCORE 4.00",
                    },
                ]
            )
        rows.append(
            {
                "id": f"marker-{split}",
                "query_id": "no-information",
                "register": "formal",
                "target": "không có thông tin",
            }
        )

    for rejection_class in VALID_REQUIREMENTS["rejection_classes"]:
        checklist[rejection_class] = []
        for split, rows in splits.items():
            for register in VALID_REQUIREMENTS["required_registers"]:
                record_id = f"{rejection_class}-{split}-{register}"
                checklist[rejection_class].append(record_id)
                rows.append(
                    {
                        "id": record_id,
                        "query_id": "no-information",
                        "register": register,
                        "target": "không có thông tin",
                    }
                )
    return splits, checklist


def test_assesses_family_register_numeric_and_rejection_coverage(tmp_path) -> None:
    requirements = load_coverage_requirements(
        _write_requirements(tmp_path, VALID_REQUIREMENTS),
        _catalogue(),
    )
    splits, checklist = _complete_splits()

    report = assess_coverage(splits, _catalogue(), requirements, checklist)

    assert report["complete"] is True
    require_complete_coverage(report)

    incomplete = {
        split: [
            row
            for row in rows
            if not (split == "train" and row["query_id"] == "academic-performance-band")
        ]
        for split, rows in splits.items()
    }
    report = assess_coverage(incomplete, _catalogue(), requirements, checklist)

    assert report["complete"] is False
    assert report["missing_numeric_cases"] == [
        {"query_id": "academic-performance-band", "split": "train", "slots": {"score": "4.00"}}
    ]
    with pytest.raises(CoverageError, match="coverage incomplete"):
        require_complete_coverage(report)
