import pytest

from ontchatbot.research.catalogue import load_catalogue
from ontchatbot.runtime.sparql import execute_select
from ontchatbot.settings import QUERY_CATALOGUE_PATH


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


def test_catalogue_detail_queries_cover_complete_official_tables(
    ontology_graph,
) -> None:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    cases = {
        "tuition-rate-details": (
            1,
            "Quyết định số 729/QĐ-ĐHNT",
            "| TT | Trình độ và hình thức đào tạo | Mức học phí |",
        ),
        "doctoral-tuition-details": (
            1,
            "Quyết định số 729/QĐ-ĐHNT",
            "MỨC HỌC PHÍ CHƯƠNG TRÌNH ĐÀO TẠO TRÌNH ĐỘ ĐẠI HỌC",
        ),
        "class-size-details": (
            1,
            "Quyết định số 1052/QĐ-ĐHNT",
            "| TT | Học phần | Số lượng sinh viên |",
        ),
        "academic-performance-details": (
            1,
            "Quyết định số 1052/QĐ-ĐHNT",
            "Điều 18. Đánh giá kết quả học tập theo học kỳ và năm học",
        ),
        "graduation-classification-details": (
            1,
            "Quyết định số 1052/QĐ-ĐHNT",
            "Điều 23. Bằng tốt nghiệp và phân loại tốt nghiệp",
        ),
        "payment-method-details": (
            3,
            "Hướng dẫn đóng học phí qua ngân hàng",
            "học phí",
        ),
    }

    for query_id, (count, document, fragment) in cases.items():
        rows = execute_select(
            ontology_graph,
            catalogue[query_id].target_template,
            max_rows=100,
        )
        assert len(rows) == count, query_id
        assert all(set(row) == {"document", "answer"} for row in rows), query_id
        assert all(row["document"] == document for row in rows), query_id
        assert any(fragment in row["answer"] for row in rows), query_id

    tuition = execute_select(
        ontology_graph,
        catalogue["tuition-rate-details"].target_template,
    )
    assert "345.000 đ/TC" in tuition[0]["answer"]
    assert "570.000 đ/TC" in tuition[0]["answer"]


@pytest.mark.parametrize(
    ("certificate", "expected_rows", "header", "relevant_rule"),
    [
        (
            ":IELTSCertificate",
            2,
            "| Khung NLNN 6 bậc | CEFR | TOEIC | TOEFL (iBT) | IELTS |",
            "| Bậc 4 | B2 | ≥ 600 | ≥ 70 | ≥ 5.5 |",
        ),
        (
            ":HSKCertificate",
            3,
            "| Khung NLNN 6 bậc | Tiếng Trung (HSK) |",
            "| Bậc 3 | HSK 3 | TOCFL 3 | N4 | 469 |",
        ),
        (
            ":IC3Certificate",
            1,
            "| TT | Điểm IC3 | Điểm ICDL | Điểm MOS | Điểm quy đổi / Điểm thưởng |",
            "| 1 | 1990 - 2329 | 1350 - 1445 | 1400 - 1599 | 8 |",
        ),
    ],
)
def test_certificate_conversion_details_return_parent_official_tables(
    ontology_graph,
    certificate: str,
    expected_rows: int,
    header: str,
    relevant_rule: str,
) -> None:
    target = load_catalogue(QUERY_CATALOGUE_PATH)[
        "certificate-conversion-details"
    ].target_template.replace("${certificate}", certificate)

    rows = execute_select(ontology_graph, target)

    assert len(rows) == expected_rows
    assert all(set(row) == {"document", "answer"} for row in rows)
    assert any(header in row["answer"] for row in rows)
    assert any(relevant_rule in row["answer"] for row in rows)


def test_certificate_conversion_details_return_tables_for_all_declared_certificates(
    ontology_graph,
) -> None:
    spec = load_catalogue(QUERY_CATALOGUE_PATH)["certificate-conversion-details"]

    for certificate in spec.slots["certificate"].values:
        target = spec.target_template.replace("${certificate}", certificate)
        rows = execute_select(ontology_graph, target)

        assert rows, certificate
        assert all("| :---" in row["answer"] for row in rows), certificate
