from __future__ import annotations

import json

import pytest

from ontchatbot.research.gate_dataset import (
    load_gate_release,
    validate_gate_release,
)


def _write_split(path, name: str, rows: list[dict[str, str]]) -> None:
    (path / f"{name}.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _valid_release() -> dict[str, list[dict[str, str]]]:
    return {
        "train": [
            {"input": "điều kiện tốt nghiệp", "label": "in_scope"},
            {"input": "thời tiết hôm nay", "label": "out_of_scope"},
        ],
        "val": [
            {"input": "đăng ký học phần sao", "label": "in_scope"},
            {"input": "viết giúp một bài thơ", "label": "out_of_scope"},
        ],
        "test": [
            {"input": "bảo lưu thế nào", "label": "in_scope"},
            {"input": "ai là tổng thống mỹ", "label": "out_of_scope"},
        ],
    }


def test_load_gate_release_requires_all_three_splits(tmp_path) -> None:
    _write_split(tmp_path, "train", _valid_release()["train"])

    with pytest.raises(FileNotFoundError, match="val.jsonl"):
        load_gate_release(tmp_path)


def test_valid_release_reports_balanced_split_counts() -> None:
    report = validate_gate_release(_valid_release())

    assert report == {
        "valid": True,
        "records": 6,
        "splits": {
            "train": {"records": 2, "in_scope": 1, "out_of_scope": 1},
            "val": {"records": 2, "in_scope": 1, "out_of_scope": 1},
            "test": {"records": 2, "in_scope": 1, "out_of_scope": 1},
        },
        "errors": [],
    }


@pytest.mark.parametrize(
    ("row", "code"),
    [
        (
            {"input": "học phí", "label": "in_scope", "origin": "old"},
            "invalid_fields",
        ),
        ({"input": "học phí", "label": "maybe"}, "invalid_label"),
        ({"input": "   ", "label": "in_scope"}, "empty_input"),
    ],
)
def test_gate_contract_rejects_malformed_rows(row, code) -> None:
    release = _valid_release()
    release["train"][0] = row

    report = validate_gate_release(release)

    assert report["valid"] is False
    assert code in {error["code"] for error in report["errors"]}


def test_gate_contract_rejects_normalized_duplicate_across_splits() -> None:
    release = _valid_release()
    release["test"][0]["input"] = "ĐIỀU KIỆN  TỐT NGHIỆP"

    report = validate_gate_release(release)

    assert report["valid"] is False
    assert "duplicate_input" in {error["code"] for error in report["errors"]}


def test_gate_contract_rejects_duplicate_that_only_differs_by_punctuation() -> None:
    release = _valid_release()
    release["test"][0]["input"] = "Điều kiện tốt nghiệp?"

    report = validate_gate_release(release)

    assert report["valid"] is False
    assert "duplicate_input" in {error["code"] for error in report["errors"]}


def test_gate_contract_rejects_imbalanced_split() -> None:
    release = _valid_release()
    release["train"].append(
        {"input": "học cải thiện ra sao", "label": "in_scope"}
    )

    report = validate_gate_release(release)

    assert report["valid"] is False
    assert "class_imbalance" in {error["code"] for error in report["errors"]}
