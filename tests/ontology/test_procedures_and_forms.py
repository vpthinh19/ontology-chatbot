from rdflib import Literal, OWL, RDF, RDFS
from rdflib.namespace import XSD


PROCEDURES = {
    "ArticulationStudyProcedure",
    "CourseRegistrationProcedure",
    "ExtraClassOpeningRequestProcedure",
    "CourseRetakeProcedure",
    "GradeImprovementProcedure",
    "GraduationProjectRegistrationProcedure",
    "ClassAbsenceRequestProcedure",
    "ExamPostponementProcedure",
    "DismissalTransferRequestProcedure",
    "CreditRecognitionProcedure",
    "CourseExemptionAndBonusProcedure",
    "GraduationReviewProcedure",
    "EarlyGraduationReviewProcedure",
    "TemporaryAcademicLeaveProcedure",
    "StudyWithdrawalProcedure",
    "StudyResumptionProcedure",
    "MajorChangeProcedure",
    "UniversityTransferProcedure",
    "StudentExchangeProcedure",
    "SecondProgramRegistrationProcedure",
    "SickLeaveProcedure",
    "TuitionPaymentProcedure",
}

FORM_TO_PROCEDURE = {
    1: "ExtraClassOpeningRequestProcedure",
    2: "GraduationProjectRegistrationProcedure",
    3: "ClassAbsenceRequestProcedure",
    4: "ExamPostponementProcedure",
    5: "DismissalTransferRequestProcedure",
    6: "CreditRecognitionProcedure",
    7: "CourseExemptionAndBonusProcedure",
    8: "EarlyGraduationReviewProcedure",
    9: "TemporaryAcademicLeaveProcedure",
    10: "StudyWithdrawalProcedure",
    11: "StudyResumptionProcedure",
    12: "MajorChangeProcedure",
    13: "UniversityTransferProcedure",
    14: "StudentExchangeProcedure",
    15: "SecondProgramRegistrationProcedure",
}

PROVISION_ROLES = {
    "eligibilityProvision",
    "instructionProvision",
    "deadlineProvision",
    "resultProvision",
}


def test_semantic_procedure_schema_and_provenance(ontology_graph, academic) -> None:
    for role in PROVISION_ROLES:
        assert (academic[role], RDF.type, OWL.ObjectProperty) in ontology_graph
        assert (academic[role], RDFS.subPropertyOf, academic.sourceProvision) in ontology_graph

    actual = set(ontology_graph.subjects(RDF.type, academic.AcademicProcedure))
    assert actual == {academic[name] for name in PROCEDURES}
    for procedure in actual:
        assert (procedure, RDF.type, OWL.NamedIndividual) in ontology_graph
        assert ontology_graph.value(procedure, academic.sourceDocument) is not None
        assert any(
            ontology_graph.value(procedure, academic[role]) is not None
            for role in PROVISION_ROLES
        )
        assert ontology_graph.value(procedure, academic.officialText) is None


def test_policy_index_points_to_exact_article_20_clauses(
    ontology_graph, academic
) -> None:
    expected = {
        academic.AcademicWarningPolicy: academic.Decision1052Article20Clause01,
        academic.AcademicDismissalPolicy: academic.Decision1052Article20Clause02,
    }
    assert set(ontology_graph.subjects(RDF.type, academic.AcademicPolicy)) == set(
        expected
    )
    for policy, provision in expected.items():
        assert (policy, RDF.type, OWL.NamedIndividual) in ontology_graph
        assert (
            policy,
            academic.sourceDocument,
            academic.Decision1052,
        ) in ontology_graph
        assert set(ontology_graph.objects(policy, academic.sourceProvision)) == {
            provision
        }
        assert ontology_graph.value(policy, academic.officialText) is None


def test_forms_follow_decision_1052_numbering(ontology_graph, academic) -> None:
    forms = set(ontology_graph.subjects(RDF.type, academic.FormDocument))
    expected = {academic[f"Decision1052Form{number:02d}"] for number in range(1, 16)}
    assert forms == expected
    for number, procedure_name in FORM_TO_PROCEDURE.items():
        form = academic[f"Decision1052Form{number:02d}"]
        procedure = academic[procedure_name]
        assert str(ontology_graph.value(form, academic.formNumber)) == f"{number:02d}"
        assert (procedure, academic.requiresForm, form) in ontology_graph


def test_scraped_catalogue_has_19_normalized_download_entries(
    ontology_graph, academic
) -> None:
    catalogue = academic.UndergraduateFormCatalogue
    assert str(ontology_graph.value(catalogue, academic.webPageUrl)) == (
        "https://pdtdaihoc.ntu.edu.vn/van-ban-phap-quy"
    )
    entries = set(ontology_graph.objects(catalogue, academic.hasCatalogueEntry))
    assert len(entries) == 19
    assert entries == set(ontology_graph.subjects(RDF.type, academic.FormCatalogueEntry))
    for entry in entries:
        url = ontology_graph.value(entry, academic.downloadUrl)
        assert isinstance(url, Literal)
        assert url.datatype == XSD.anyURI
        assert str(url).startswith("https://pdtdaihoc.ntu.edu.vn/")
        assert "/uploads/" in str(url).lower()
        assert ".." not in str(url)
        assert ontology_graph.value(entry, academic.listedTitle).language == "vi"


def test_old_catalogue_numbers_are_not_joined_to_new_forms(ontology_graph, academic) -> None:
    old_temporary_leave = next(
        entry
        for entry in ontology_graph.subjects(RDF.type, academic.FormCatalogueEntry)
        if "nghỉ học tạm thời" in str(ontology_graph.value(entry, academic.listedTitle)).lower()
    )
    old_course_preservation = next(
        entry
        for entry in ontology_graph.subjects(RDF.type, academic.FormCatalogueEntry)
        if "bảo lưu học phần" in str(ontology_graph.value(entry, academic.listedTitle)).lower()
    )
    assert (old_temporary_leave, academic.catalogueEntryForForm, academic.Decision1052Form08) not in ontology_graph
    assert (old_course_preservation, academic.catalogueEntryForForm, academic.Decision1052Form14) not in ontology_graph


def test_procedures_link_exact_source_provisions_by_semantic_role(
    ontology_graph, academic
) -> None:
    expected = {
        academic.eligibilityProvision: {
            academic.ArticulationStudyProcedure: {
                academic.Decision1052Article29Clause01
            },
            academic.ClassAbsenceRequestProcedure: {
                academic.Decision1052Article17Clause01PointA,
                academic.Decision1052Article30Clause01,
            },
            academic.CourseExemptionAndBonusProcedure: {academic.Decision1052Article21Clause05},
            academic.CourseRegistrationProcedure: {
                academic.Decision1052Article09Clause03,
                academic.Decision1052Article09Clause04,
                academic.Decision1052Article09Clause05,
            },
            academic.CourseRetakeProcedure: {
                academic.Decision1052Article11Clause01,
                academic.Decision1052Article11Clause02,
                academic.Decision1052Article11Clause03,
            },
            academic.CreditRecognitionProcedure: {
                academic.Decision1052Article21Clause03,
                academic.Decision1052Article21Clause04,
                academic.Decision1052Article21Clause07,
            },
            academic.DismissalTransferRequestProcedure: {academic.Decision1052Article20Clause03},
            academic.EarlyGraduationReviewProcedure: {
                academic.Decision1052Article22Clause01,
                academic.Decision1052Article22Clause02,
            },
            academic.ExamPostponementProcedure: {
                academic.Decision1052Article17Clause04,
                academic.Decision1052Article30Clause02,
            },
            academic.ExtraClassOpeningRequestProcedure: {academic.Decision1052Article10Clause02},
            academic.GradeImprovementProcedure: {academic.Decision1052Article11Clause03},
            academic.GraduationProjectRegistrationProcedure: {
                academic.Decision1052Article14Clause01,
                academic.Decision1052Article14Clause02,
            },
            academic.GraduationReviewProcedure: {academic.Decision1052Article22Clause01},
            academic.MajorChangeProcedure: {academic.Decision1052Article25Clause01},
            academic.SecondProgramRegistrationProcedure: {academic.Decision1052Article28Clause01},
            academic.SickLeaveProcedure: {
                academic.Decision1052Article30Clause01,
                academic.Decision1052Article30Clause02,
            },
            academic.StudentExchangeProcedure: {academic.Decision1052Article27Clause03},
            academic.StudyResumptionProcedure: {academic.Decision1052Article24Clause03},
            academic.StudyWithdrawalProcedure: {academic.Decision1052Article24Clause02},
            academic.TemporaryAcademicLeaveProcedure: {
                academic.Decision1052Article24Clause01,
                academic.Decision1052Article30Clause01,
            },
            academic.UniversityTransferProcedure: {academic.Decision1052Article26Clause01},
        },
        academic.deadlineProvision: {
            academic.ArticulationStudyProcedure: {
                academic.Decision1052Article29Clause02
            },
            academic.ClassAbsenceRequestProcedure: {
                academic.Decision1052Article17Clause01PointA,
                academic.Decision1052Article30Clause01,
            },
            academic.EarlyGraduationReviewProcedure: {
                academic.Decision1052Article22Clause05,
                academic.Decision1052Article22Clause06,
            },
            academic.ExamPostponementProcedure: {
                academic.Decision1052Article17Clause04,
                academic.Decision1052Article30Clause02,
            },
            academic.ExtraClassOpeningRequestProcedure: {academic.Decision1052Article10Clause02},
            academic.GraduationReviewProcedure: {
                academic.Decision1052Article22Clause05,
                academic.Decision1052Article22Clause06,
            },
            academic.MajorChangeProcedure: {academic.Decision1052Article25Clause02},
            academic.SecondProgramRegistrationProcedure: {
                academic.Decision1052Article28Clause03PointA,
                academic.Decision1052Article28Clause05,
            },
            academic.SickLeaveProcedure: {
                academic.Decision1052Article30Clause01,
                academic.Decision1052Article30Clause02,
            },
            academic.StudentExchangeProcedure: {academic.Decision1052Article27Clause04PointA},
            academic.StudyResumptionProcedure: {academic.Decision1052Article24Clause03},
        },
        academic.resultProvision: {
            academic.CourseExemptionAndBonusProcedure: {academic.Decision1052Article21Clause05},
            academic.CourseRetakeProcedure: {academic.Decision1052Article11Clause04},
            academic.CreditRecognitionProcedure: {
                academic.Decision1052Article21Clause01,
                academic.Decision1052Article21Clause04,
            },
            academic.DismissalTransferRequestProcedure: {academic.Decision1052Article20Clause03},
            academic.EarlyGraduationReviewProcedure: {
                academic.Decision1052Article22Clause04,
                academic.Decision1052Article22Clause05,
            },
            academic.ExamPostponementProcedure: {academic.Decision1052Article17Clause04},
            academic.ExtraClassOpeningRequestProcedure: {academic.Decision1052Article10Clause02},
            academic.GradeImprovementProcedure: {academic.Decision1052Article11Clause04},
            academic.GraduationProjectRegistrationProcedure: {academic.Decision1052Article14Clause04},
            academic.GraduationReviewProcedure: {
                academic.Decision1052Article22Clause04,
                academic.Decision1052Article22Clause05,
            },
            academic.MajorChangeProcedure: {academic.Decision1052Article25Clause03},
            academic.SecondProgramRegistrationProcedure: {
                academic.Decision1052Article28Clause02,
                academic.Decision1052Article28Clause03PointB,
                academic.Decision1052Article28Clause03PointC,
                academic.Decision1052Article28Clause03PointD,
            },
            academic.StudentExchangeProcedure: {
                academic.Decision1052Article27Clause01,
                academic.Decision1052Article27Clause02,
            },
            academic.StudyResumptionProcedure: {academic.Decision1052Article24Clause03},
            academic.StudyWithdrawalProcedure: {academic.Decision1052Article24Clause02},
            academic.TemporaryAcademicLeaveProcedure: {academic.Decision1052Article24Clause01},
            academic.UniversityTransferProcedure: {academic.Decision1052Article26Clause02PointB},
        },
    }

    for predicate, procedures in expected.items():
        for procedure, provisions in procedures.items():
            assert set(ontology_graph.objects(procedure, predicate)) == provisions
            assert all(ontology_graph.value(provision, academic.officialText) for provision in provisions)

    assert not list(
        ontology_graph.objects(
            academic.ClassAbsenceRequestProcedure,
            academic.resultProvision,
        )
    )


def test_articles_20_29_and_30_have_precise_instruction_paths(
    ontology_graph, academic
) -> None:
    expected = {
        academic.ArticulationStudyProcedure: {academic.Decision1052Article29},
        academic.SickLeaveProcedure: {academic.Decision1052Article30},
        academic.TemporaryAcademicLeaveProcedure: {
            academic.Decision1052Article24,
            academic.Decision1052Article30Clause01,
        },
        academic.ExamPostponementProcedure: {
            academic.Decision1052Article17,
            academic.Decision1052Article30Clause02,
        },
        academic.ClassAbsenceRequestProcedure: {
            academic.Decision1052Article17,
            academic.Decision1052Article30Clause01,
        },
        academic.DismissalTransferRequestProcedure: {
            academic.Decision1052Article20Clause03,
        },
    }
    for procedure, provisions in expected.items():
        assert set(
            ontology_graph.objects(procedure, academic.instructionProvision)
        ) == provisions


def test_only_sourced_academic_actors_exist(ontology_graph, academic) -> None:
    expected = {
        "Student",
        "University",
        "UniversityPresident",
        "AcademicManagementUnit",
        "StudentAffairsOffice",
        "FacultyOrInstitute",
        "Department",
        "ProfessionalCouncil",
        "GraduationCouncil",
    }
    assert set(ontology_graph.subjects(RDF.type, academic.AcademicActor)) == {
        academic[name] for name in expected
    }
