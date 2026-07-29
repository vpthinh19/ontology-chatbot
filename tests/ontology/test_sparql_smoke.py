import pytest

from ontchatbot.runtime.sparql import execute_select


@pytest.mark.parametrize(
    ("query", "column", "fragment"),
    [
        (
            "SELECT ?answer WHERE { :CourseRegistrationProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "Đăng ký khối lượng học tập",
        ),
        (
            "SELECT ?answer WHERE { :CourseRetakeProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "học lại",
        ),
        (
            "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "nghỉ học tạm thời",
        ),
        (
            "SELECT ?answer WHERE { :MajorChangeProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "Chuyển ngành",
        ),
        (
            "SELECT ?answer WHERE { :GraduationReviewProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "Điều kiện xét tốt nghiệp",
        ),
        (
            "SELECT ?answer WHERE { :AcademicDismissalPolicy :sourceProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "Vượt quá 02 lần cảnh báo",
        ),
        (
            "SELECT ?answer WHERE { :ArticulationStudyProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "Học liên thông",
        ),
        (
            "SELECT ?answer WHERE { :SickLeaveProcedure :instructionProvision ?part . ?part :officialText ?answer . }",
            "answer",
            "xin nghỉ ốm",
        ),
    ],
)
def test_procedure_queries_return_official_text(
    ontology_graph, query, column, fragment
) -> None:
    rows = execute_select(ontology_graph, query)
    assert rows
    assert fragment.lower() in str(rows[0][column]).lower()


def test_form_download_query_returns_literal_url(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?url WHERE { :TemporaryAcademicLeaveProcedure :requiresForm ?form . ?entry :catalogueEntryForForm ?form ; :downloadUrl ?url . }",
    )
    assert len(rows) == 1
    assert str(rows[0]["url"]).startswith("https://pdtdaihoc.ntu.edu.vn/uploads/")


def test_tuition_query_filters_by_program_and_cohort(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?amount ?cohort WHERE { ?rate a :TuitionRate ; :appliesToProgram :InformationTechnology ; :appliesToCourseCategory :AccreditedFoundationAndMajorCourse ; :minimumCohortNumber ?cohort ; :amount ?amount . FILTER (?cohort <= 66) } ORDER BY DESC(?cohort) LIMIT 1",
    )
    assert rows == [{"amount": 620000, "cohort": 65}]


def test_payment_query_returns_four_method_labels(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?answer WHERE { :TuitionPaymentProcedure :supportsPaymentMethod ?method . ?method rdfs:label ?answer . } ORDER BY ?answer",
    )
    assert len(rows) == 4
    assert any("VNPAY" in row["answer"] for row in rows)


def test_performance_band_query_uses_numeric_filter(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?answer WHERE { ?band a :AcademicPerformanceBand ; :minimumValue ?minimum ; :maximumValue ?maximum ; :resultLabel ?answer . FILTER (?minimum <= 8.5 && 8.5 <= ?maximum) }",
    )
    assert rows == [{"answer": "Giỏi"}]


def test_class_size_query_returns_cnc_limits(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?minimum ?maximum WHERE { :CNCPracticeClassSizeRule :minimumValue ?minimum ; :maximumValue ?maximum . }",
    )
    assert rows == [{"minimum": "10.0", "maximum": "15.0"}]


def test_language_certificate_query_returns_source_criterion(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        'SELECT ?answer WHERE { ?rule a :CertificateConversionRule ; :appliesToCertificate :IELTSCertificate ; :mapsToCompetencyLevel :VietnameseFrameworkLevel4 ; :criterionText ?answer . FILTER (?answer = "≥ 5.5"@vi) }',
    )
    assert rows == [{"answer": "≥ 5.5"}]


def test_computer_certificate_query_converts_score(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?answer WHERE { ?rule a :CertificateConversionRule ; :appliesToCertificate :IC3Certificate ; :minimumScore ?minimum ; :maximumScore ?maximum ; :convertedGrade ?answer . FILTER (?minimum <= 2400 && 2400 <= ?maximum) }",
    )
    assert rows == [{"answer": "9.0"}]
