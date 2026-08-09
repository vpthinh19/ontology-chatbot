"""Nội dung bản phát hành: chạy được, phủ đủ, và không tự mâu thuẫn.

Mọi luật ở đây đối chiếu với **artifact thật** chứ không chốt cứng con số, theo
đúng cách ``test_public_docs_quote_the_real_catalogue_size`` đã làm: không tệp
test nào được giữ một con số mà chỉ nó biết.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
from rdflib import RDF, Namespace

from ontchatbot.cli import validate_data
from ontchatbot.catalogue import QuerySpec, SlotSpec, load_catalogue, match_target
from ontchatbot.research.coverage import (
    assess_coverage,
    load_coverage_requirements,
    require_complete_coverage,
)
from ontchatbot.research.dataset import load_release, validate_release
from ontchatbot.runtime.sparql import SparqlError, execute_select, load_ontology
from ontchatbot.settings import (
    COVERAGE_REQUIREMENTS_PATH,
    DATASET_DIR,
    QUERY_CATALOGUE_PATH,
)

ACADEMIC = Namespace("http://www.ntu.edu.vn/ontology/academic#")
CHECKLIST_PATH = Path("resources/cases/rejection_checklist.json")
USER_QUERIES_PATH = Path("resources/cases/user_queries.json")
#: Thuộc tính của lược đồ CŨ, đã bỏ. Đích nào còn dùng chúng là dấu hiệu lược đồ
#: cũ sống lại.
RETIRED_PROPERTIES = (
    ":content",
    ":condition",
    ":outcome",
    ":handledBy",
    ":receivedBy",
    ":instructionProvision",
    ":eligibilityProvision",
    ":deadlineProvision",
    ":resultProvision",
    ":sourceProvision",
)
LOCAL_NAME = re.compile(r":([A-Za-z][A-Za-z0-9]*)")


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(QUERY_CATALOGUE_PATH)


@pytest.fixture(scope="module")
def release():
    return load_release()


@pytest.fixture(scope="module")
def graph():
    return load_ontology()


@pytest.fixture(scope="module")
def checklist():
    return json.loads(CHECKLIST_PATH.read_text(encoding="utf-8"))


def _coverage_fixture_catalogue() -> dict[str, QuerySpec]:
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


def _complete_coverage_fixture() -> tuple[
    dict[str, list[dict[str, str]]], dict[str, list[str]]
]:
    splits = {split: [] for split in ("train", "val", "test")}
    checklist = {"hard-negative": []}
    for split, rows in splits.items():
        for register in ("formal", "neutral", "colloquial", "noisy"):
            rows.extend(
                [
                    {
                        "id": f"procedure-{split}-{register}",
                        "query_id": "procedure-family",
                        "register": register,
                        "target": "PROCEDURE :Procedure",
                    },
                    {
                        "id": f"score-{split}-{register}",
                        "query_id": "academic-performance-band",
                        "register": register,
                        "target": "SCORE 4.00",
                    },
                ]
            )
            record_id = f"hard-negative-{split}-{register}"
            checklist["hard-negative"].append(record_id)
            rows.append(
                {
                    "id": record_id,
                    "query_id": "no-information",
                    "register": register,
                    "target": "không có thông tin",
                }
            )
    return splits, checklist


def test_complete_coverage_fixture_is_accepted(tmp_path) -> None:
    catalogue = _coverage_fixture_catalogue()
    coverage_path = tmp_path / "coverage.json"
    coverage_path.write_text(
        json.dumps(
            {
                "priority_domains": ["procedure"],
                "numeric_cases": [
                    {
                        "query_id": "academic-performance-band",
                        "split": "train",
                        "slots": {"score": "4.00"},
                    }
                ],
                "rejection_classes": ["hard-negative"],
                "required_registers": ["formal", "neutral", "colloquial", "noisy"],
            }
        ),
        encoding="utf-8",
    )
    release, checklist = _complete_coverage_fixture()

    report = assess_coverage(
        release,
        catalogue,
        load_coverage_requirements(coverage_path, catalogue),
        checklist,
    )

    assert report["complete"] is True
    require_complete_coverage(report)


def test_validation_cli_reports_complete_canonical_chain(monkeypatch, capsys) -> None:
    """Lệnh kiểm tra phải báo chuỗi đầy đủ, đối chiếu với chính danh mục.

    Bản trước chốt ``supported_entries == 2953``. Sau refactor ontology con số
    thật là 6.073, và test chỉ nói "khác nhau" chứ không cho biết bên nào đúng.
    """

    monkeypatch.setattr(sys, "argv", ["validate_sparql_dataset"])

    validate_data.main()

    payload = json.loads(capsys.readouterr().out)
    assert payload["release"]["catalogue_coverage_required"] is True
    assert payload["catalogue"]["supported_entries"] > 0
    assert (
        payload["catalogue"]["covered_entries"]
        == payload["catalogue"]["supported_entries"]
    )
    assert payload["catalogue"]["uncovered_entries"] == []
    assert payload["coverage"]["complete"] is True
    assert payload["artifacts"]["mismatches"] == []
    # "stale" là trạng thái ĐÚNG cho tới khi huấn luyện lại trên dataset mới.
    assert payload["provenance"]["model_metrics"]["status"] in ("current", "stale")


def test_official_release_is_executable_and_has_complete_coverage(
    graph, catalogue, release, checklist
) -> None:
    """Bản phát hành phải chạy được và phủ đủ danh mục.

    Bản trước còn đòi một danh sách họ ``procedure-*`` viết cứng trong tệp test.
    Danh mục v2 đổi tiền tố thành ``academic-procedure-*``, nên danh sách đó chỉ
    còn là ký ức về một bản khác. Thay bằng: mọi họ primary trong miền quy trình
    đều phải có mặt trong danh mục và được dạy.
    """

    release_report = validate_release(release, graph, catalogue)
    coverage_report = assess_coverage(
        release,
        catalogue,
        load_coverage_requirements(COVERAGE_REQUIREMENTS_PATH, catalogue),
        checklist,
    )
    taught = {row["query_id"] for row in release["train"]}
    primary_procedures = {
        query_id
        for query_id, spec in catalogue.items()
        if spec.domain == "procedure" and spec.tier == "primary"
    }

    assert primary_procedures
    assert primary_procedures <= taught
    assert release_report["catalogue_coverage_required"] is True
    assert release_report["domains"]["procedure"] > 0
    assert coverage_report["complete"] is True
    require_complete_coverage(coverage_report)


def test_every_target_returns_data_from_the_ontology(graph, catalogue, release) -> None:
    """Không đích nào được rỗng ruột.

    Dạy model sinh một truy vấn hợp lệ mà không bao giờ trả về dòng nào nghĩa là
    dạy nó dẫn người dùng tới "Không có thông tin" cho câu hỏi ĐÁNG LẼ trả lời
    được. Đây là ràng buộc số 4 của ``docs/DATASET.md``.
    """

    marker = catalogue["no-information"].target_template
    empty = []
    for target in sorted({row["target"] for rows in release.values() for row in rows}):
        if target == marker:
            continue
        try:
            rows = execute_select(graph, target, max_rows=500)
        except SparqlError:
            # Vượt trần dòng nghĩa là CÓ dữ liệu, rất nhiều là khác.
            continue
        if not rows:
            empty.append(target)

    assert empty == []


def test_certificate_conversion_targets_stay_compact(catalogue, graph) -> None:
    """Họ quy đổi chứng chỉ phải trả BẢNG quy đổi, không trả cả khối văn bản.

    Bản trước chốt cứng một chuỗi SPARQL của họ ``certificate-conversion-details``
    - họ đó không còn tồn tại. Ý định thì còn nguyên: câu hỏi quy đổi phải nhận
    được các mốc điểm, không phải nguyên văn điều luật.
    """

    spec = catalogue["certificate-criterion"]
    rows = execute_select(graph, spec.target_template.replace(
        "${certificate}", spec.slots["certificate"].values[0]
    ), max_rows=50)

    assert rows
    for row in rows:
        for value in row.values():
            assert len(str(value)) <= 500, value


def test_tuition_targets_answer_with_a_rate_not_a_wall_of_text(catalogue, graph) -> None:
    """Hỏi học phí phải nhận được MỘT mức tiền, không phải nguyên văn quyết định."""

    spec = catalogue["tuition-program-cohort-rate"]
    target = spec.target_template.replace(
        "${program}", spec.slots["program"].values[0]
    ).replace("${cohort}", "65")
    rows = execute_select(graph, target, max_rows=10)

    assert len(rows) == 1
    for value in rows[0].values():
        assert len(str(value)) <= 100, value


def test_declared_slot_iris_exist_in_the_ontology(graph, catalogue) -> None:
    """Mọi IRI khai trong danh mục phải là node có thật.

    Khai một neo không tồn tại là dạy model sinh truy vấn luôn rỗng. Bản trước
    còn đòi neo của miền ``procedure`` phải thuộc lớp ``AcademicProcedure``;
    miền đó gồm cả TRƯỜNG HỢP học vụ ("nhập ngũ", "lý do cá nhân") nên điều kiện
    ấy sai - đúng chỗ đã khiến bộ sinh ghép mẫu câu bẫy với thực thể sai loại.
    """

    existing = {str(node).rsplit("#", 1)[-1] for node in graph.subjects()}
    declared = {
        value
        for spec in catalogue.values()
        for slot in spec.slots.values()
        if slot.kind == "iri"
        for value in slot.values
    }

    assert declared
    assert sorted(value for value in declared if value[1:] not in existing) == []


def test_procedure_outcome_slots_exclude_procedures_without_an_outcome(
    catalogue,
) -> None:
    """Chỉ thủ tục thật sự có kết quả xử lý mới được liệt kê.

    Nếu slot liệt kê cả thủ tục không khai kết quả, model sẽ học sinh ra một
    truy vấn hợp lệ nhưng luôn rỗng - và người dùng nhận "không có thông tin"
    cho một câu hỏi đáng lẽ trả lời được bằng cách khác.
    """

    result_procedures = set(
        catalogue["academic-procedure-has-outcome-outcome-text"].slots["anchor"].values
    )

    assert result_procedures.isdisjoint(
        {":CourseExemptionAndBonusProcedure", ":StudyResumptionProcedure"}
    )
    assert ":GraduationReviewProcedure" in result_procedures


def test_targets_never_resurrect_the_retired_schema(release) -> None:
    """Không đích nào được dùng lại thuộc tính của lược đồ cũ.

    Lược đồ cũ để bốn khía cạnh của cùng một thủ tục trỏ về gần như cùng một đoạn
    văn - khiến model nhận đúng thực thể nhưng chọn sai quan hệ.

    Bản trước còn cấm đích trỏ THẲNG vào node điều/khoản/điểm. Ràng buộc đó nay
    sai: tra cứu nguyên văn một điều luật là năng lực CÓ CHỦ ĐÍCH của v2.
    """

    # So theo TOÁN TỬ trọn vẹn, không so chuỗi con: v2 có ``:conditionText`` hợp
    # lệ, mà ``:condition`` là chuỗi con của nó.
    retired = re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(re.escape(n) for n in RETIRED_PROPERTIES) + r")(?![A-Za-z0-9])"
    )
    offending = [
        (row["query_id"], match.group(1))
        for rows in release.values()
        for row in rows
        for match in [retired.search(row["target"])]
        if match
    ]

    assert offending == []


def test_every_finite_slot_value_is_taught(graph, catalogue, release) -> None:
    """Mọi giá trị slot hữu hạn phải xuất hiện ở train.

    Bản trước liệt kê tay 14 họ và chốt cứng "29 ngành, 15 chứng chỉ ngoại ngữ,
    3 chứng chỉ tin học, 14 quy tắc quy mô lớp". Những con số đó là ảnh chụp một
    ontology đã đổi. Ràng buộc thật thì không cần con số nào: model không thể
    sinh ra một neo nó chưa từng thấy.
    """

    report = validate_release(release, graph, catalogue)
    missing = {
        query_id: {
            name: details["missing_train"]
            for name, details in slots.items()
            if details["missing_train"]
        }
        for query_id, slots in report["slot_coverage"].items()
    }

    assert {k: v for k, v in missing.items() if v} == {}


def test_rejection_checklist_partitions_every_declared_class(
    release, catalogue, checklist
) -> None:
    """Danh sách nhóm câu từ chối phải ĐỌC từ ``coverage.json``.

    Bản trước chốt cứng bảy nhóm trong chính tệp test, nên khi nhóm "câu hỏi
    pha" được chuyển sang câu trả lời được, test đỏ vì lý do sai: nó tưởng dữ
    liệu hỏng, thật ra chính nó đang giữ một quyết định đã bị thay.

    Từ phiên 2 có HAI đích từ chối: câu ngoài phạm vi nhận danh sách năng lực,
    câu gần miền vẫn nhận ``không có thông tin``. Cả hai đều là cách xử lý một
    câu hỏi không trả lời trực tiếp được.
    """

    required = json.loads(
        (DATASET_DIR / "coverage.json").read_text(encoding="utf-8")
    )["rejection_classes"]
    rows_by_id = {
        row["id"]: (split, row) for split, rows in release.items() for row in rows
    }
    handled_domains = {"out-of-domain", "assistant"}

    assert sorted(checklist) == sorted(required)
    listed = [row_id for ids in checklist.values() for row_id in ids]
    assert len(listed) == len(set(listed))
    for rejection_class, row_ids in checklist.items():
        assert {
            (rows_by_id[row_id][0], rows_by_id[row_id][1]["register"])
            for row_id in row_ids
        } == {
            (split, register)
            for split in ("train", "val", "test")
            for register in ("formal", "neutral", "colloquial", "noisy")
        }, rejection_class
        for row_id in row_ids:
            row = rows_by_id[row_id][1]
            spec = catalogue[row["query_id"]]
            assert spec.domain in handled_domains, (rejection_class, row["query_id"])
            assert match_target(spec, row["target"]) is not None


def test_every_real_user_question_has_a_declared_expectation(catalogue) -> None:
    """Câu hỏi do NGƯỜI THẬT gõ phải có một quyết định rõ ràng.

    Bảy câu đầu là của người dùng thật; hai câu cuối do **giảng viên chủ nhiệm
    đề tài** test. Bản trước bắt buộc từng câu phải nằm nguyên văn trong dataset
    - bộ sinh v2 tự viết cách diễn đạt riêng nên điều đó không còn đúng, và cũng
    không nên đúng: đây là bộ thử nghiệm chạy trên MODEL sau khi huấn luyện,
    không phải dữ liệu huấn luyện.

    Cái phải canh là: mỗi câu có một họ truy vấn được chỉ định, và họ đó có thật.
    """

    payload = json.loads(USER_QUERIES_PATH.read_text(encoding="utf-8"))
    questions = [
        line
        for line in Path("resources/cases/user_queries.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    expectations = {
        item["question"]: item["expected_query_id"]
        for item in payload["expectations"]
    }

    assert sorted(expectations) == sorted(questions)
    assert sorted(set(expectations.values()) - set(catalogue)) == []
    # Hai câu của giảng viên phải còn trong bộ - chúng là bằng chứng người thật
    # duy nhất mà dự án có.
    assert "Bạn có thể hỗ trợ thông tin gì" in expectations
    assert expectations["Bạn có thể hỗ trợ thông tin gì"] == "assistant-capabilities"


def test_the_cohort_tuition_question_resolves_to_one_rate(graph, catalogue) -> None:
    """"hc phí k65 cntt" phải ra đúng MỘT mức học phí.

    Bản trước chốt cứng id dòng ``question-002000`` và nguyên văn chuỗi SPARQL.
    Cả hai đều là ảnh chụp của một lần sinh dataset. Ràng buộc thật là về NĂNG
    LỰC: khoá 65 ngành Công nghệ thông tin phải quy về một mức duy nhất.
    """

    spec = catalogue["tuition-program-cohort-rate"]
    target = spec.target_template.replace(
        "${program}", ":InformationTechnology"
    ).replace("${cohort}", "65")

    rows = execute_select(graph, target, max_rows=10)

    assert len(rows) == 1
    assert match_target(spec, target) is not None


def test_procedure_families_are_taught_thickly_enough_to_learn(
    catalogue, release
) -> None:
    """Mỗi họ quy trình phải đủ dày để model học được HÌNH DẠNG truy vấn.

    Bản trước chốt một ma trận histogram chính xác tới từng đích (``{10: 99,
    14: 4, 16: 4, ...}``) - đó là ảnh chụp của một lần sinh, đổi một hạt giống
    ngẫu nhiên là đỏ. Ý định thì còn: mỗi hình dạng truy vấn phải được nhìn thấy
    đủ nhiều, và đủ bốn phong cách.
    """

    procedures = {
        query_id
        for query_id, spec in catalogue.items()
        if spec.domain == "procedure" and spec.tier == "primary"
    }
    counts = Counter(
        row["query_id"] for row in release["train"] if row["query_id"] in procedures
    )
    registers = {
        query_id: {
            row["register"]
            for row in release["train"]
            if row["query_id"] == query_id
        }
        for query_id in procedures
    }

    assert sorted(procedures - set(counts)) == []
    assert sorted(q for q, n in counts.items() if n < 10) == []
    assert sorted(q for q, r in registers.items() if len(r) < 4) == []


def test_every_evaluated_target_was_taught_first(release) -> None:
    """Đích nào đem ra chấm cũng phải từng được dạy.

    Chiều ngược lại KHÔNG bắt buộc và cố ý không bắt buộc: val/test chỉ lấy mẫu
    một phần neo, vì chúng đo cách hỏi mới chứ không đo trí nhớ thêm thực thể.
    """

    trained = {row["target"] for row in release["train"]}

    for split in ("val", "test"):
        unseen = sorted({row["target"] for row in release[split]} - trained)
        assert unseen == [], split


def test_the_manifest_matches_the_files_it_describes() -> None:
    """Manifest phải khớp chính tệp nó mô tả.

    Bản trước đóng băng sha256 của val/test trong tệp test. Đóng băng ở đó chỉ
    chốt lại MỘT lần sinh; ràng buộc thật là manifest và dữ liệu không được lệch
    nhau, và nó tự đúng qua mọi lần sinh lại.
    """

    from ontchatbot.research.reporting import sha256_file

    manifest = json.loads(
        (DATASET_DIR / "manifest.json").read_text(encoding="utf-8")
    )

    for split, entry in manifest["files"].items():
        path = DATASET_DIR / entry["path"]
        assert entry["sha256"] == sha256_file(path), split
        assert entry["records"] == len(
            [line for line in path.read_text(encoding="utf-8").splitlines() if line]
        )
    assert manifest["catalogue"]["sha256"] == sha256_file(QUERY_CATALOGUE_PATH)


def test_registers_stay_balanced_across_the_training_set(release) -> None:
    """Bốn phong cách phải cân nhau trong tập huấn luyện.

    Bản trước chốt số dòng chính xác của từng "lô phục hồi" trong một đợt vá
    dataset đã qua (``{"noisy": 314, "neutral": 224, ...}``) - những lô đó không
    còn tồn tại. Tính chất mà chúng bảo vệ thì còn: không phong cách nào bị bỏ
    rơi, nếu không model sẽ giỏi hẳn ở văn viết và dốt hẳn ở câu gõ vội.
    """

    counts = Counter(row["register"] for row in release["train"])

    assert set(counts) == {"formal", "neutral", "colloquial", "noisy"}
    assert min(counts.values()) / max(counts.values()) >= 0.7, counts
