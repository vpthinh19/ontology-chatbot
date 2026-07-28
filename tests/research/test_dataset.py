from __future__ import annotations

from copy import deepcopy

import pytest

from ontchatbot.research.dataset import DatasetError, load_release, validate_release
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import DATASET_DIR


TARGETS = (
    "SELECT ?answer WHERE { :AcademicLeaveProcedure :content ?answer . }",
    "SELECT ?answer WHERE { :CourseRegistrationProcedure :content ?answer . }",
)
QUESTIONS = (
    (
        "Tôi cần hướng dẫn nghỉ học tạm thời",
        "thủ tục bảo lưu kết quả học tập",
        "xin phép tạm dừng chương trình đang học",
        "sắp đi nghĩa vụ quân sự thì làm sao giữ kết quả",
        "hướng dẫn bảo lưu kết quả học tập gồm những gì",
        "tui muốn nghỉ học tạm thời thì làm sao",
    ),
    (
        "Tôi cần hướng dẫn đăng ký học phần",
        "cách chọn môn cho học kỳ mới",
        "quy trình ghi danh môn học thực hiện thế nào",
        "muốn thêm lớp vào thời khóa biểu phải làm sao",
        "hướng dẫn thực hiện đăng ký học phần",
        "dk mon hoc ky moi sao vay",
    ),
)
REGISTERS = ("formal", "neutral", "colloquial", "noisy")


def _valid_release(query_count: int = 1) -> dict[str, list[dict[str, str]]]:
    release: dict[str, list[dict[str, str]]] = {
        "train": [],
        "val": [],
        "test": [],
    }
    for index in range(query_count):
        query_id = f"query-{index + 1:04d}"
        target = TARGETS[index]
        questions = QUESTIONS[index]
        rows = [
            {
                "id": f"question-{index + 1:04d}-{offset}",
                "query_id": query_id,
                "register": REGISTERS[(index * 2 + offset) % len(REGISTERS)],
                "input": question,
                "target": target,
            }
            for offset, question in enumerate(questions)
        ]
        release["train"].extend(rows[:2])
        release["val"].extend(rows[2:4])
        release["test"].extend(rows[4:6])
    return release


def test_canonical_dataset_is_executable() -> None:
    if not DATASET_DIR.is_dir():
        pytest.skip("SPARQL dataset has not been generated")
    report = validate_release(load_release(), load_ontology())

    assert report["records"] == 2263
    assert report["split_counts"] == {"train": 1403, "val": 430, "test": 430}
    assert all(split["queries"] == 215 for split in report["splits"].values())
    assert all(not split["empty_result_ids"] for split in report["splits"].values())


def test_validator_accepts_the_in_domain_query_contract() -> None:
    release = _valid_release()

    report = validate_release(release, load_ontology())

    assert report["records"] == 6
    assert all(
        set(row) == {"id", "query_id", "register", "input", "target"}
        for rows in release.values()
        for row in rows
    )
    assert report["splits"]["train"]["queries"] == 1


def test_validator_rejects_one_query_id_with_two_targets() -> None:
    release = _valid_release(query_count=2)
    for rows in release.values():
        for row in rows:
            row["query_id"] = "query-0001"

    with pytest.raises(DatasetError, match="query IDs have multiple targets"):
        validate_release(release, load_ontology())


def test_validator_rejects_one_target_with_two_query_ids() -> None:
    release = _valid_release(query_count=2)
    for rows in release.values():
        for row in rows:
            row["target"] = TARGETS[0]

    with pytest.raises(DatasetError, match="targets have multiple query IDs"):
        validate_release(release, load_ontology())


def test_validator_rejects_query_id_missing_from_a_split() -> None:
    release = _valid_release(query_count=2)
    release["val"] = [row for row in release["val"] if row["query_id"] != "query-0002"]

    with pytest.raises(DatasetError, match="query IDs missing from splits"):
        validate_release(release, load_ontology())


def test_validator_rejects_fewer_than_two_train_rows_per_query() -> None:
    release = _valid_release()
    release["train"].pop()

    with pytest.raises(DatasetError, match="fewer than two train rows"):
        validate_release(release, load_ontology())


def test_validator_rejects_register_imbalance() -> None:
    release = _valid_release()
    for offset in (5, 6):
        release["train"].append(
            {
                **release["train"][0],
                "id": f"question-extra-{offset}",
                "input": f"câu hỏi bổ sung hoàn toàn khác số {offset}",
            }
        )

    with pytest.raises(DatasetError, match="register counts differ by more than one"):
        validate_release(release, load_ontology())


@pytest.mark.parametrize("field", ["id", "input"])
def test_validator_rejects_exact_cross_split_leakage(field: str) -> None:
    release = _valid_release()
    release["test"][0][field] = release["train"][0][field]

    with pytest.raises(DatasetError, match=f"{field}s? cross splits"):
        validate_release(release, load_ontology())


def test_validator_rejects_near_duplicate_questions_across_splits() -> None:
    release = _valid_release()
    release["train"][0]["input"] = (
        "Liệt kê hai mức học phí mỗi tín chỉ khác nhau cao nhất của khóa K66"
    )
    release["test"][0]["input"] = (
        "Liệt kê hai mức học phí mỗi tín chỉ khác nhau cao nhất của khóa K65"
    )

    with pytest.raises(DatasetError, match="near-duplicate questions cross splits"):
        validate_release(release, load_ontology())


def test_validator_rejects_removed_query_shape_field() -> None:
    release = deepcopy(_valid_release())
    release["train"][0]["query_shape"] = "direct"

    with pytest.raises(DatasetError, match="fields must be exactly"):
        validate_release(release, load_ontology())
