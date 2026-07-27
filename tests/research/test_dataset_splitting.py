from collections import Counter

import pytest

from ontchatbot.research.dataset import (
    DatasetError,
    _cross_split_near_duplicates,
    build_in_domain_release,
    load_release,
)


def _source_rows(count: int = 4) -> list[dict[str, str]]:
    target = "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }"
    return [
        {
            "id": f"question-{index}",
            "family_id": "family-1",
            "register": register,
            "input": f"cách hỏi bảo lưu riêng biệt số {index}",
            "target": target,
        }
        for index, register in enumerate(
            ("formal", "neutral", "colloquial", "noisy")[:count],
            1,
        )
    ]


def test_in_domain_split_preserves_content_and_covers_every_query() -> None:
    current = load_release()
    source = [row for split in ("train", "val", "test") for row in current[split]]

    release = build_in_domain_release(source)

    assert {name: len(rows) for name, rows in release.items()} == {
        "train": 1150,
        "val": 215,
        "test": 215,
    }
    assert {
        name: len({row["query_id"] for row in rows})
        for name, rows in release.items()
    } == {"train": 215, "val": 215, "test": 215}
    assert min(Counter(row["query_id"] for row in release["train"]).values()) == 2
    assert Counter(
        (row["id"], row["register"], row["input"], row["target"])
        for row in source
    ) == Counter(
        (row["id"], row["register"], row["input"], row["target"])
        for rows in release.values()
        for row in rows
    )
    register_counts = {
        split: Counter(row["register"] for row in rows)
        for split, rows in release.items()
    }
    assert all(
        max(counts.values()) - min(counts.values()) <= 1
        for counts in register_counts.values()
    )
    assert _cross_split_near_duplicates(release) == []
    assert build_in_domain_release(
        [row for rows in release.values() for row in rows]
    ) == release


def test_splitter_rejects_duplicate_ids_before_allocating() -> None:
    rows = _source_rows()
    rows[1]["id"] = rows[0]["id"]

    with pytest.raises(DatasetError, match="duplicate id"):
        build_in_domain_release(rows)


def test_splitter_rejects_target_with_fewer_than_four_questions() -> None:
    with pytest.raises(DatasetError, match="at least four questions"):
        build_in_domain_release(_source_rows(count=3))
