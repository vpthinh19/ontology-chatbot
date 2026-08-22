"""Đồ thị đã lắp phải trả lời được từng miền, qua đúng đường mà runtime dùng.

Các kiểm tra ở đây chạy SPARQL thật qua ``execute_select`` nên chúng đồng thời
xác nhận ràng buộc an toàn của runtime: chỉ ``SELECT``, và kết quả phải là nhãn
hoặc literal chứ không phải node.
"""

import json

import pytest

from ontchatbot.runtime.render import render_rows
from ontchatbot.runtime.sparql import execute_select


def answers(graph, query: str) -> list[str]:
    return [str(value) for row in execute_select(graph, query) for value in row.values()]


# ------------------------------------------------------------- quy trình
def test_a_procedure_answers_with_its_own_steps_in_order(ontology_graph) -> None:
    """Điều 24 chứa ba thủ tục; câu hỏi về bảo lưu không được lẫn phần thôi học."""

    steps = answers(
        ontology_graph,
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :hasStep ?s . "
        "?s :stepOrder ?o ; :stepText ?answer . } ORDER BY ?o",
    )

    assert steps == [
        "Viết đơn xin nghỉ học tạm thời theo Mẫu số 09 (Phụ lục 4).",
        "Gửi đơn tới Hiệu trưởng thông qua Phòng Công tác Chính trị và Sinh viên.",
    ]
    assert not any("thôi học" in step for step in steps)


def test_no_relation_points_at_a_node_that_does_not_exist(ontology_graph) -> None:
    """Tham chiếu treo là lỗi im lặng: truy vấn vẫn hợp lệ nhưng trả về rỗng.

    Kiểm tra này đã bắt một quy trình trỏ tới :VNPayGatewayPayment trong khi
    phương thức thanh toán thật tên là :VNPAYPayment.
    """

    from rdflib import OWL, RDF, URIRef

    from ontchatbot.settings import ONTOLOGY_NS

    declared = {
        node
        for node in ontology_graph.subjects(RDF.type, None)
        if isinstance(node, URIRef) and str(node).startswith(ONTOLOGY_NS)
    }
    relations = {
        node
        for node in ontology_graph.subjects(RDF.type, OWL.ObjectProperty)
        if str(node).startswith(ONTOLOGY_NS)
    }
    dangling = sorted(
        f"{str(subject).rsplit('#', 1)[-1]} :{str(relation).rsplit('#', 1)[-1]} "
        f"-> {str(target).rsplit('#', 1)[-1]}"
        for relation in relations
        for subject, target in ontology_graph.subject_objects(relation)
        if isinstance(target, URIRef) and target not in declared
    )

    assert dangling == []


def test_a_situation_reaches_the_procedure_that_handles_it(ontology_graph) -> None:
    handled = answers(
        ontology_graph,
        "SELECT ?answer WHERE { :ArmedForcesCase :hasResolution ?r . "
        "?r :resolvedBy ?p . ?p rdfs:label ?answer . }",
    )

    assert handled == ["Thủ tục nghỉ học tạm thời"]


def test_an_ambiguous_situation_returns_its_branching_conditions(ontology_graph) -> None:
    """Ốm dẫn tới ba thủ tục, nên câu trả lời phải là tiêu chí phân nhánh."""

    rows = execute_select(
        ontology_graph,
        "SELECT ?condition ?procedure WHERE { :IllnessCase :hasResolution ?r . "
        "?r :conditionText ?condition ; :resolvedBy ?p . ?p rdfs:label ?procedure . } "
        "ORDER BY ?condition",
    )

    assert len(rows) == 3
    assert {row["procedure"] for row in rows} == {
        "Thủ tục nghỉ học tạm thời",
        "Thủ tục xin nghỉ ốm trong quá trình học",
        "Thủ tục xin hoãn thi",
    }


def test_conditions_are_returned_as_separate_items(ontology_graph) -> None:
    conditions = answers(
        ontology_graph,
        "SELECT ?answer WHERE { :MajorChangeProcedure :hasRequirement ?r . "
        "?r :requirementOrder ?n ; :requirementText ?answer . } ORDER BY ?n",
    )

    assert len(conditions) == 4
    assert conditions[0].startswith("Không đang là sinh viên năm thứ nhất")


# --------------------------------------------------------------- nguồn
def test_a_fact_can_be_traced_back_to_its_article(ontology_graph) -> None:
    assert answers(
        ontology_graph,
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :basedOn ?p . "
        "?p :citationLabel ?answer . }",
    ) == [
        "Điều 24 Quy chế đào tạo trình độ đại học Trường Đại học Nha Trang, "
        "ban hành kèm Quyết định 1052/QĐ-ĐHNT ngày 17/7/2025"
    ]


def test_a_citation_tells_the_reader_where_to_verify_it(ontology_graph) -> None:
    """Người hỏi không biết "Quyết định 1052" là văn bản nào. Trích dẫn phải tự
    nói ra: điều nào, của văn bản gì, ban hành ngày nào - và kèm nơi tra cứu."""

    rows = execute_select(
        ontology_graph,
        "SELECT ?căncứ ?xemtại WHERE { :MajorChangeProcedure :basedOn ?p . "
        "?p :citationLabel ?căncứ ; :documentUrl ?xemtại . }",
    )

    assert len(rows) == 1
    citation = str(rows[0]["căncứ"])
    assert "Điều 25" in citation
    assert "1052/QĐ-ĐHNT" in citation
    assert "17/7/2025" in citation
    assert str(rows[0]["xemtại"]).startswith("https://")


def test_a_provision_can_be_found_by_its_number(ontology_graph) -> None:
    found = answers(
        ontology_graph,
        "SELECT ?answer WHERE { ?p :articleNumber 25 ; :clauseNumber 1 ; "
        ':pointLetter "c" ; :officialText ?answer . }',
    )

    assert found and "Trưởng Khoa" in found[0]


# ------------------------------------------------------------- đơn vị
def test_an_office_answers_more_than_its_name(ontology_graph) -> None:
    rows = execute_select(
        ontology_graph,
        "SELECT ?name ?phone WHERE { :ExamPostponementProcedure :submittedTo ?u . "
        "?u rdfs:label ?name ; :officePhone ?phone . }",
    )

    assert rows == [{"name": "Phòng Đào tạo Đại học", "phone": "0258 3831148"}]


# -------------------------------------------------------------- học phí
#
# Mức học phí phụ thuộc khoá, ngành, chương trình và học phần đã đăng ký, thay đổi
# từng kỳ, và trang sinhvien.ntu.edu.vn mới công bố đúng cho từng sinh viên.
# Ontology mô hình hoá cách thanh toán, là dữ kiện ổn định có nguồn.
def test_payment_methods_are_listed(ontology_graph) -> None:
    methods = answers(
        ontology_graph,
        "SELECT ?answer WHERE { :TuitionPaymentProcedure :supportsPaymentMethod ?m . "
        "?m rdfs:label ?answer . }",
    )

    assert len(methods) == 4


# ------------------------------------------------------------ chứng chỉ
def test_certificate_conversion_is_returned_as_six_whole_tables(ontology_graph) -> None:
    tables = answers(
        ontology_graph,
        "SELECT ?answer WHERE { ?table a :CertificateConversionTable ; "
        ":verbatimTableText ?answer . }",
    )

    assert len(tables) == 6
    # Chọn bảng bằng cột đặc trưng, không bằng thứ tự trả về. Hai bảng cùng liệt
    # kê "Công nghệ thông tin" nhưng mô tả các nhóm chứng chỉ khác nhau; truy vấn
    # không có mệnh đề sắp xếp nên thứ tự không phải tiêu chí phân biệt.
    special_english_tables = [
        text
        for text in tables
        if "IELTS" in text.splitlines()[0] and "Công nghệ thông tin" in text
    ]
    assert len(special_english_tables) == 1
    special_english = special_english_tables[0]
    assert "| 1 | Công nghệ thông tin | Bậc 4 hoặc B2 | ≥ 600 | ≥ 5.0 | ≥ 65 |" in special_english
    assert "| 1 | Công nghệ thông tin | Bậc 4 hoặc B2 | ≥ 600 | ≥ 65 | ≥ 5.0 |" not in special_english


# ------------------------------------------------------------ biểu mẫu
def test_a_procedure_reaches_its_downloadable_form(ontology_graph) -> None:
    urls = answers(
        ontology_graph,
        "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :requiresForm ?f . "
        "?e :catalogueEntryForForm ?f ; :downloadUrl ?answer . }",
    )

    assert urls and urls[0].startswith("https://pdtdaihoc.ntu.edu.vn/")


def test_the_form_catalogue_lists_every_entry(ontology_graph) -> None:
    """Danh mục biểu mẫu có đúng 18 mục.

    Trang nguồn liệt kê "Mẫu số 5" và "Mẫu số 5A" thành hai dòng, nhưng chúng
    trỏ tới cùng một tờ đơn với hai tệp tải khác nhau, nên ontology gộp thành
    một mục mang cả hai đường tải và cả hai số hiệu.
    """
    titles = answers(
        ontology_graph,
        "SELECT ?answer WHERE { ?e a :FormCatalogueEntry ; :listedTitle ?answer . }",
    )

    assert len(titles) == 18


# ------------------------------------------------------------ an toàn
def test_a_query_returning_a_node_is_refused(ontology_graph) -> None:
    from ontchatbot.runtime.sparql import SparqlError

    with pytest.raises(SparqlError):
        execute_select(
            ontology_graph,
            "SELECT ?answer WHERE { :TemporaryAcademicLeaveProcedure :submittedTo ?answer . }",
        )


def test_answers_reach_the_agent_as_data_not_prose(ontology_graph) -> None:
    """Công cụ trả dữ liệu cho mô hình điều phối, không trả câu chữ.

    Người dùng đọc câu do mô hình viết, nên chỗ này không dựng câu. Nó dựng dữ
    kiện kèm trạng thái tường minh để mô hình biết đã đủ dữ liệu hay chưa.
    """

    rendered = json.loads(
        render_rows(
            execute_select(
                ontology_graph,
                "SELECT ?answer WHERE { :MajorChangeProcedure :hasDeadline ?d . "
                "?d :deadlineText ?answer . }",
            )
        )
    )

    assert rendered["trang_thai"] == "co_du_lieu"
    assert rendered["du_lieu"] == [
        {"answer": "Nộp đơn ít nhất 02 tuần trước khi bắt đầu học kỳ mới."}
    ]
