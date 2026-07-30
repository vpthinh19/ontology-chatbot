from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
from rdflib import RDF, Namespace

from ontchatbot.cli import validate_data
from ontchatbot.research.catalogue import QuerySpec, SlotSpec, load_catalogue
from ontchatbot.research.coverage import (
    assess_coverage,
    load_coverage_requirements,
    require_complete_coverage,
)
from ontchatbot.research.dataset import load_release, validate_release
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import COVERAGE_REQUIREMENTS_PATH, QUERY_CATALOGUE_PATH


ACADEMIC = Namespace("http://www.ntu.edu.vn/ontology/academic#")
PROCEDURE_FAMILIES = {
    "procedure-instruction",
    "procedure-eligibility",
    "procedure-deadline",
    "procedure-result",
    "procedure-submission-office",
    "procedure-review-office",
    "procedure-required-form",
    "procedure-form-download",
    "procedure-overview",
    "procedure-list",
    "procedure-source",
    "procedure-decision-authority",
}
SECONDARY_FAMILIES = {
    "tuition-program-cohort-rate",
    "payment-method-list",
    "payment-bank-list",
    "payment-fee",
    "payment-warning",
    "form-list",
    "form-download",
    "academic-performance-band",
    "study-year-band",
    "graduation-classification-band",
    "class-size-rule",
    "language-certificate-level",
    "certificate-criterion",
    "computer-certificate-grade",
}
REJECTION_CLASSES = {
    "greeting-social",
    "unrelated",
    "near-domain-missing",
    "ambiguous",
    "noisy-out-of-domain",
    "mixed",
    "hard-negative",
}
USER_QUERY_EXPECTATIONS = {
    "chào bạn nha": "no-information",
    "đăng ký hc phần như nào nhỉ": "procedure-instruction",
    "đăng ký học phần sao": "procedure-instruction",
    "vì sao lại đăng ký học phần": "no-information",
    "đk hc phần như thế nào": "procedure-instruction",
    "hc phí k65 cntt": "tuition-program-cohort-rate",
    "học phí k67 như thế nào": "no-information",
}
FROZEN_VAL_SHA256 = "063495561b0025b681d96b9b1fc569208a81cd919dfeeb505c1b10ad1da82669"
FROZEN_TEST_SHA256 = "7e8cc503a9da1478ab448eca6fcce2adec13771720085ccb06b294c7db336305"
SOURCE_TYPES = {
    ACADEMIC.Chapter,
    ACADEMIC.Article,
    ACADEMIC.Clause,
    ACADEMIC.Point,
}
LOCAL_NAME = re.compile(r":([A-Za-z][A-Za-z0-9]*)")


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


def test_validation_cli_prints_release_and_coverage_summaries_when_complete(
    monkeypatch, capsys
) -> None:
    release_summary = {"records": 1}
    coverage_summary = {"complete": True}
    monkeypatch.setattr(validate_data, "load_release", lambda _: {"release": []})
    monkeypatch.setattr(validate_data, "load_ontology", lambda: object())
    monkeypatch.setattr(
        validate_data,
        "validate_release",
        lambda release, graph, catalogue=None, **kwargs: release_summary,
    )
    monkeypatch.setattr(
        validate_data,
        "load_catalogue",
        lambda _: {"query-0001": object()},
        raising=False,
    )
    monkeypatch.setattr(
        validate_data,
        "load_coverage_requirements",
        lambda path, catalogue: object(),
        raising=False,
    )
    monkeypatch.setattr(
        validate_data,
        "_load_rejection_checklist",
        lambda _: {"hard-negative": []},
        raising=False,
    )
    monkeypatch.setattr(
        validate_data,
        "assess_coverage",
        lambda release, catalogue, requirements, checklist: coverage_summary,
        raising=False,
    )
    monkeypatch.setattr(
        validate_data,
        "require_complete_coverage",
        lambda report: None,
        raising=False,
    )
    monkeypatch.setattr(sys, "argv", ["validate_sparql_dataset"])

    validate_data.main()

    assert json.loads(capsys.readouterr().out) == {
        "release": release_summary,
        "coverage": coverage_summary,
    }


def test_official_release_is_executable_and_has_complete_coverage() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    release = load_release()
    checklist = json.loads(
        Path("resources/cases/rejection_checklist.json").read_text(encoding="utf-8")
    )

    release_report = validate_release(release, graph, catalogue)
    coverage_report = assess_coverage(
        release,
        catalogue,
        load_coverage_requirements(COVERAGE_REQUIREMENTS_PATH, catalogue),
        checklist,
    )

    assert PROCEDURE_FAMILIES <= set(catalogue)
    assert release_report["catalogue_coverage_required"] is True
    assert release_report["domains"]["procedure"] > 0
    assert coverage_report["complete"] is True
    require_complete_coverage(coverage_report)


def test_certificate_conversion_detail_rows_use_compact_parent_table_targets() -> None:
    expected_template = (
        "SELECT DISTINCT ?document ?answer WHERE { ?rule a :CertificateConversionRule ; "
        ":appliesToCertificate ${certificate} ; :sourceDocument/rdfs:label ?document ; "
        ":sourceProvision/:partOf/:officialText ?answer . }"
    )
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    spec = catalogue["certificate-conversion-details"]
    release = load_release()
    rows = {
        split: [
            row
            for row in split_rows
            if row["query_id"] == "certificate-conversion-details"
        ]
        for split, split_rows in release.items()
    }
    expected_targets = {
        expected_template.replace("${certificate}", certificate)
        for certificate in spec.slots["certificate"].values
    }

    assert spec.target_template == expected_template
    assert {split: len(split_rows) for split, split_rows in rows.items()} == {
        "train": 38,
        "val": 6,
        "test": 5,
    }
    assert {row["target"] for split_rows in rows.values() for row in split_rows} == (
        expected_targets
    )


def test_tuition_rate_detail_rows_use_compact_official_table_target() -> None:
    expected_template = (
        "SELECT DISTINCT ?document ?answer WHERE { ?rate a :TuitionRate ; "
        ":sourceDocument/rdfs:label ?document ; "
        ":sourceProvision/:officialText ?answer . }"
    )
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    release = load_release()
    rows = {
        split: [
            row for row in split_rows if row["query_id"] == "tuition-rate-details"
        ]
        for split, split_rows in release.items()
    }

    assert catalogue["tuition-rate-details"].target_template == expected_template
    assert {split: len(split_rows) for split, split_rows in rows.items()} == {
        "train": 16,
        "val": 3,
        "test": 3,
    }
    assert {
        row["target"] for split_rows in rows.values() for row in split_rows
    } == {expected_template}


def test_official_procedure_iris_exist_in_ontology() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    report = validate_release(load_release(), graph, catalogue)
    existing = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.AcademicProcedure)
    }
    declared = {
        value
        for spec in catalogue.values()
        if spec.domain == "procedure"
        for slot in spec.slots.values()
        for value in slot.values
    }
    seen = {
        value
        for query_id, slots in report["slot_coverage"].items()
        if catalogue[query_id].domain == "procedure"
        for details in slots.values()
        for value in details["seen_train"]
    }

    assert declared <= existing
    assert seen <= existing


def test_procedure_result_slots_exclude_non_result_procedures() -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    result_procedures = set(
        catalogue["procedure-result"].slots["procedure"].values
    )

    assert result_procedures.isdisjoint(
        {
            ":CourseExemptionAndBonusProcedure",
            ":StudyResumptionProcedure",
        }
    )


@pytest.mark.parametrize(
    ("input_text", "query_id", "provision_role"),
    [
        (
            "Những thành tích hoặc chứng chỉ nào giúp sinh viên được xem xét miễn học, miễn thi hay cộng điểm thưởng?",
            "procedure-eligibility",
            ":eligibilityProvision",
        ),
        (
            "Sau thời gian bảo lưu, sinh viên cần làm thủ tục xin học trở lại như thế nào?",
            "procedure-instruction",
            ":instructionProvision",
        ),
    ],
)
def test_reviewed_procedure_rows_use_semantically_supported_provision_roles(
    input_text: str,
    query_id: str,
    provision_role: str,
) -> None:
    rows = {
        row["input"]: row
        for split in load_release().values()
        for row in split
    }

    assert rows[input_text]["query_id"] == query_id
    assert provision_role in rows[input_text]["target"]


def test_targets_do_not_restore_old_schema_or_query_source_nodes_directly() -> None:
    graph = load_ontology()
    rows = [row for split in load_release().values() for row in split]
    forbidden_properties = (":content", ":condition", ":outcome", ":handledBy", ":receivedBy")

    for row in rows:
        target = row["target"]
        assert not any(name in target for name in forbidden_properties)
        for local_name in LOCAL_NAME.findall(target):
            resource = ACADEMIC[local_name]
            assert not any((resource, RDF.type, source_type) in graph for source_type in SOURCE_TYPES)


def test_secondary_query_families_cover_finite_ontology_values() -> None:
    graph = load_ontology()
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    report = validate_release(load_release(), graph, catalogue)

    assert SECONDARY_FAMILIES <= set(catalogue)

    expected_programs = {
        f":{str(program).rsplit('#', 1)[-1]}"
        for rate in graph.subjects(RDF.type, ACADEMIC.TuitionRate)
        for program in graph.objects(rate, ACADEMIC.appliesToProgram)
    }
    expected_language_certificates = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.LanguageCertificate)
    }
    expected_computer_certificates = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.ComputerCertificate)
    }
    # Class-size rows are represented directly as rules; the ontology does not
    # attach synthetic CourseCategory nodes to these official table rows.
    expected_class_size_rules = {
        f":{str(node).rsplit('#', 1)[-1]}"
        for node in graph.subjects(RDF.type, ACADEMIC.ClassSizeRule)
    }

    assert len(expected_programs) == 29
    assert len(expected_language_certificates) == 15
    assert len(expected_computer_certificates) == 3
    assert len(expected_class_size_rules) == 14
    assert expected_programs <= set(
        catalogue["tuition-program-cohort-rate"].slots["program"].values
    )
    assert expected_language_certificates <= set(
        catalogue["certificate-criterion"].slots["certificate"].values
    )
    assert expected_computer_certificates <= set(
        catalogue["computer-certificate-grade"].slots["certificate"].values
    )
    assert expected_class_size_rules <= set(
        catalogue["class-size-rule"].slots["rule"].values
    )

    for query_id in SECONDARY_FAMILIES:
        for details in report["slot_coverage"][query_id].values():
            assert details["missing_train"] == []


def test_rejection_checklist_exactly_partitions_all_seven_classes() -> None:
    splits = load_release()
    checklist_path = Path("resources/cases/rejection_checklist.json")
    checklist = json.loads(checklist_path.read_text(encoding="utf-8"))
    rows_by_id = {
        row["id"]: (split, row)
        for split, rows in splits.items()
        for row in rows
    }

    assert set(checklist) == REJECTION_CLASSES
    released_ids = [row_id for ids in checklist.values() for row_id in ids]
    assert len(released_ids) == len(set(released_ids))
    assert set(released_ids) == {
        row["id"]
        for rows in splits.values()
        for row in rows
        if row["query_id"] == "no-information"
    }
    for rejection_class, row_ids in checklist.items():
        assert {
            (rows_by_id[row_id][0], rows_by_id[row_id][1]["register"])
            for row_id in row_ids
        } == {
            (split, register)
            for split in ("train", "val", "test")
            for register in ("formal", "neutral", "colloquial", "noisy")
        }, (rejection_class, row_ids)
        for row_id in row_ids:
            row = rows_by_id[row_id][1]
            assert row["query_id"] == "no-information"
            assert row["target"] == "không có thông tin"


def test_every_real_user_query_has_an_explicit_released_decision() -> None:
    queries = Path("resources/cases/user_queries.txt").read_text(encoding="utf-8").splitlines()
    release = load_release()
    matches = [
        (split, row)
        for split, rows in release.items()
        for row in rows
        if row["input"] in queries
    ]
    occurrences = Counter(row["input"] for _, row in matches)
    actual = {
        row["input"]: (split, row["query_id"])
        for split, row in matches
    }

    assert queries == list(USER_QUERY_EXPECTATIONS)
    assert occurrences == Counter({query: 1 for query in queries})
    assert actual == {
        query: ("test", query_id)
        for query, query_id in USER_QUERY_EXPECTATIONS.items()
    }


def test_preprocessed_cntt_tuition_query_is_supported() -> None:
    release = load_release()
    row = next(
        row
        for row in release["test"]
        if row["id"] == "question-002000"
    )
    checklist = json.loads(
        Path("resources/cases/rejection_checklist.json").read_text(encoding="utf-8")
    )

    assert row["query_id"] == "tuition-program-cohort-rate"
    assert row["target"] == (
        "SELECT ?answer WHERE { ?rate :appliesToProgram :InformationTechnology ; "
        ":appliesToEducationLevel :UndergraduateLevel ; :amount ?answer . OPTIONAL { "
        "?rate :minimumCohortNumber ?minimum . } FILTER (!BOUND(?minimum) || "
        "65 >= ?minimum) } ORDER BY DESC(?minimum) LIMIT 1"
    )
    assert all(row["id"] not in ids for ids in checklist.values())


def test_procedure_first_target_coverage() -> None:
    release = load_release()
    procedure = {
        split: [row for row in rows if row["query_id"].startswith("procedure-")]
        for split, rows in release.items()
    }
    train_counts = Counter(row["target"] for row in procedure["train"])
    instruction_targets = {
        row["target"]
        for row in procedure["train"]
        if row["query_id"] == "procedure-instruction"
    }
    required_registers = {"formal", "neutral", "colloquial", "noisy"}

    assert len(train_counts) == 142
    assert min(train_counts.values()) >= 10
    assert all(train_counts[target] >= 14 for target in instruction_targets)
    assert Counter(train_counts.values()) == Counter(
        {
            10: 99,
            14: 4,
            16: 4,
            18: 8,
            26: 4,
            30: 17,
            34: 2,
            46: 2,
            48: 1,
            52: 1,
        }
    )
    for target in train_counts:
        assert {
            row["register"]
            for row in procedure["train"]
            if row["target"] == target
        } == required_registers
    for target in instruction_targets:
        rows = [row for row in procedure["train"] if row["target"] == target]
        assert sum(row["query_id"] == "procedure-instruction" for row in rows) >= 6
        assert sum(row["query_id"] == "procedure-overview" for row in rows) >= 4

    course_target = (
        "SELECT ?answer WHERE { :CourseRegistrationProcedure "
        ":instructionProvision ?part . ?part :officialText ?answer . }"
    )
    assert train_counts[course_target] >= 20
    assert len(procedure["train"]) >= 2 * sum(
        row["query_id"] == "no-information" for row in release["train"]
    )
    for split in ("val", "test"):
        counts = Counter(row["target"] for row in procedure[split])
        assert set(train_counts) <= set(counts)
        assert all(counts[target] >= 2 for target in instruction_targets)
        for target in instruction_targets:
            query_ids = {
                row["query_id"]
                for row in procedure[split]
                if row["target"] == target
            }
            assert {"procedure-instruction", "procedure-overview"} <= query_ids
        course_rows = [
            row for row in procedure[split] if row["target"] == course_target
        ]
        assert len(course_rows) >= 4
        assert {row["register"] for row in course_rows} == required_registers


def test_final_release_matrix_and_frozen_evaluation_checksums() -> None:
    release = load_release()

    assert {split: len(rows) for split, rows in release.items()} == {
        "train": 3_645,
        "val": 402,
        "test": 407,
    }
    val_payload = Path("resources/dataset/val.jsonl").read_bytes()
    test_payload = Path("resources/dataset/test.jsonl").read_bytes()
    assert hashlib.sha256(val_payload).hexdigest() == FROZEN_VAL_SHA256
    assert hashlib.sha256(test_payload).hexdigest() == FROZEN_TEST_SHA256


def test_balanced_recovery_batches_match_locked_contract() -> None:
    rows = load_release()["train"]
    numbered = {
        int(row["id"].rsplit("-", 1)[-1]): row
        for row in rows
        if row["id"].startswith("question-")
    }
    new = [numbered[number] for number in range(5777, 6673)]

    assert len(new) == 896
    assert Counter(row["register"] for row in new) == Counter(
        {"noisy": 314, "neutral": 224, "colloquial": 224, "formal": 134}
    )

    a1 = [numbered[number] for number in range(5777, 5953)]
    a2 = [numbered[number] for number in range(5953, 6129)]
    for batch in (a1, a2):
        assert len(batch) == 176
        assert {row["query_id"] for row in batch} == {"procedure-instruction"}
        assert Counter(Counter(row["target"] for row in batch).values()) == Counter(
            {16: 11}
        )
        assert Counter(row["register"] for row in batch) == Counter(
            {"noisy": 62, "neutral": 44, "colloquial": 44, "formal": 26}
        )

    block_b = [numbered[number] for number in range(6129, 6273)]
    assert Counter(Counter(row["target"] for row in block_b).values()) == Counter(
        {16: 9}
    )
    assert Counter(row["register"] for row in block_b) == Counter(
        {"noisy": 50, "neutral": 36, "colloquial": 36, "formal": 22}
    )

    block_c = [numbered[number] for number in range(6273, 6493)]
    assert {row["query_id"] for row in block_c} == {"no-information"}
    assert {row["target"] for row in block_c} == {"không có thông tin"}
    assert Counter(row["register"] for row in block_c) == Counter(
        {"noisy": 77, "neutral": 55, "colloquial": 55, "formal": 33}
    )

    block_d = [numbered[number] for number in range(6493, 6673)]
    assert Counter(row["query_id"] for row in block_d) == Counter(
        {
            "class-size-rule": 14,
            "academic-actor-list": 12,
            "doctoral-tuition-details": 12,
            "form-download": 12,
            "payment-method-details": 12,
            "payment-method-list": 11,
            "payment-bank-list": 11,
            "payment-fee": 11,
            "payment-warning": 11,
            "academic-performance-band": 11,
            "academic-program-details": 11,
            "certificate-conversion-details": 11,
            "class-size-details": 11,
            "form-document-details": 10,
            "graduation-classification-band": 10,
            "official-document-metadata": 10,
        }
    )
    assert Counter(row["register"] for row in block_d) == Counter(
        {"noisy": 63, "neutral": 45, "colloquial": 45, "formal": 27}
    )


def test_recovered_training_set_strengthens_measured_weak_families() -> None:
    counts = Counter(row["query_id"] for row in load_release()["train"])
    recovered_families = {
        "academic-actor-list",
        "academic-performance-details",
        "academic-program-details",
        "certificate-details",
        "class-size-details",
        "competency-level-details",
        "course-exemption-details",
        "guidance-document-details",
        "learner-category-details",
        "payment-fee",
        "payment-fee-details",
        "payment-method-details",
        "payment-method-list",
        "payment-warning",
        "reference-entity-list",
        "tuition-rate-details",
    }

    assert {query_id: counts[query_id] for query_id in recovered_families} == {
        "academic-actor-list": 26,
        "academic-performance-details": 14,
        "academic-program-details": 25,
        "certificate-details": 14,
        "class-size-details": 25,
        "competency-level-details": 14,
        "course-exemption-details": 14,
        "guidance-document-details": 14,
        "learner-category-details": 16,
        "payment-fee": 27,
        "payment-fee-details": 14,
        "payment-method-details": 26,
        "payment-method-list": 27,
        "payment-warning": 27,
        "reference-entity-list": 12,
        "tuition-rate-details": 16,
    }
