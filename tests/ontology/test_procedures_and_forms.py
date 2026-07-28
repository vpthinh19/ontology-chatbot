from rdflib import Literal, OWL, RDF, RDFS
from rdflib.namespace import XSD


PROCEDURES = {
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
