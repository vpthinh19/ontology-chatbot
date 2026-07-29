from __future__ import annotations

import json
import re
import sys
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
    "hc phí k65 cntt": "no-information",
    "học phí k67 như thế nào": "no-information",
}
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
        "train": 18,
        "val": 2,
        "test": 2,
    }
    assert {row["target"] for split_rows in rows.values() for row in split_rows} == (
        expected_targets
    )


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
    actual = {
        row["input"]: (split, row["query_id"])
        for split, rows in release.items()
        for row in rows
        if row["input"] in queries
    }

    assert queries == list(USER_QUERY_EXPECTATIONS)
    assert actual == {
        query: ("test", query_id)
        for query, query_id in USER_QUERY_EXPECTATIONS.items()
    }
