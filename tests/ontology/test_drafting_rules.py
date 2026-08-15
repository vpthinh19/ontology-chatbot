"""Quy tắc biên soạn tầng nghiệp vụ.

Tầng nghiệp vụ được viết tay nên nó là nơi duy nhất có thể sai nội dung học vụ mà
không ai phát hiện. Mỗi kiểm tra dưới đây ứng với một lỗi **đã thực sự xảy ra**
khi soạn thảo, không phải quy tắc phòng xa. Diễn giải đầy đủ ở docs/ONTOLOGY.md.
"""

import re

from rdflib import RDF, RDFS, SKOS, Literal, URIRef

from ontchatbot.settings import ONTOLOGY_NS

#: Node mang câu trả lời thì bắt buộc dẫn nguồn.
SOURCED_CLASSES = (
    "AcademicProcedure",
    "AcademicPolicy",
    "ProcedureStep",
    "Requirement",
    "Deadline",
    "Outcome",
    "Consequence",
    "AcademicCase",
    "CaseResolution",
)
DOCUMENT_CLASSES = (
    "Chapter",
    "Article",
    "Clause",
    "Point",
    "Appendix",
    "DocumentTable",
    "CertificateConversionTable",
    "DocumentSection",
)
TEXT_PROPERTIES = (
    "summaryText",
    "stepText",
    "requirementText",
    "caseText",
    "conditionText",
    "deadlineText",
    "outcomeText",
    "consequenceText",
)


def A(name: str) -> URIRef:
    return URIRef(ONTOLOGY_NS + name)


def local(node) -> str:
    return str(node).rsplit("#", 1)[-1]


def typed(graph, class_name: str) -> set:
    return set(graph.subjects(RDF.type, A(class_name)))


def test_every_answer_bearing_node_cites_a_document_part(ontology_graph) -> None:
    parts = {node for name in DOCUMENT_CLASSES for node in typed(ontology_graph, name)}
    unsourced = sorted(
        local(node)
        for class_name in SOURCED_CLASSES
        for node in typed(ontology_graph, class_name)
        if not set(ontology_graph.objects(node, A("basedOn"))) & parts
    )

    assert unsourced == []


def test_a_requirement_limited_to_one_case_declares_its_scope(ontology_graph) -> None:
    """Bản nháp từng gắn "phải học ít nhất 01 học kỳ" cho cả thủ tục nghỉ học tạm
    thời, trong khi Điều 24 chỉ áp cho điểm d - lý do cá nhân. Người đi nghĩa vụ
    quân sự vì thế bị trả nhầm điều kiện không liên quan."""

    case_sources = {
        source
        for case in typed(ontology_graph, "AcademicCase")
        for source in ontology_graph.objects(case, A("basedOn"))
    }
    unscoped = sorted(
        local(requirement)
        for requirement in typed(ontology_graph, "Requirement")
        if not list(ontology_graph.objects(requirement, A("scopedToCase")))
        and set(ontology_graph.objects(requirement, A("basedOn"))) & case_sources
    )

    assert unscoped == []


def test_a_case_reaching_several_procedures_says_when_each_applies(ontology_graph) -> None:
    """Không có SPARQL xác định duy nhất cho "em ốm dài ngày thì sao": ốm dẫn tới
    ba thủ tục. Điều kiện phân nhánh phải được khai, không được chọn bừa."""

    ambiguous = []
    for case in typed(ontology_graph, "AcademicCase"):
        resolutions = list(ontology_graph.objects(case, A("hasResolution")))
        procedures = {
            procedure
            for resolution in resolutions
            for procedure in ontology_graph.objects(resolution, A("resolvedBy"))
        }
        if len(procedures) < 2:
            continue
        ambiguous += [
            f"{local(case)}/{local(resolution)}"
            for resolution in resolutions
            if not list(ontology_graph.objects(resolution, A("conditionText")))
        ]

    assert sorted(ambiguous) == []


def test_every_case_leads_to_at_least_one_procedure(ontology_graph) -> None:
    orphans = sorted(
        local(case)
        for case in typed(ontology_graph, "AcademicCase")
        if not list(ontology_graph.objects(case, A("hasResolution")))
    )

    assert orphans == []


def test_steps_are_numbered_from_one_without_gaps(ontology_graph) -> None:
    broken = []
    for procedure in typed(ontology_graph, "AcademicProcedure"):
        steps = list(ontology_graph.objects(procedure, A("hasStep")))
        orders = [
            int(value)
            for step in steps
            for value in ontology_graph.objects(step, A("stepOrder"))
        ]
        if not steps or sorted(orders) != list(range(1, len(steps) + 1)):
            broken.append(f"{local(procedure)}: {sorted(orders)}")

    assert sorted(broken) == []


def test_requirements_are_ordered_without_duplicates(ontology_graph) -> None:
    broken = []
    for procedure in typed(ontology_graph, "AcademicProcedure"):
        requirements = list(ontology_graph.objects(procedure, A("hasRequirement")))
        ranks = [
            int(value)
            for requirement in requirements
            for value in ontology_graph.objects(requirement, A("requirementOrder"))
        ]
        if len(ranks) != len(requirements) or len(set(ranks)) != len(ranks):
            broken.append(local(procedure))

    assert sorted(broken) == []


def test_a_deadline_or_outcome_is_not_copied_into_a_step(ontology_graph) -> None:
    """Hai bản sao của cùng một dữ kiện sẽ lệch nhau khi cập nhật."""

    duplicated = []
    for procedure in typed(ontology_graph, "AcademicProcedure"):
        step_texts = [
            str(text)
            for step in ontology_graph.objects(procedure, A("hasStep"))
            for text in ontology_graph.objects(step, A("stepText"))
        ]
        for link, text_property in (("hasDeadline", "deadlineText"), ("hasOutcome", "outcomeText")):
            for node in ontology_graph.objects(procedure, A(link)):
                for text in ontology_graph.objects(node, A(text_property)):
                    value = str(text).strip().rstrip(".")
                    if value and any(value in step for step in step_texts):
                        duplicated.append(f"{local(procedure)}/{local(node)}")

    assert sorted(duplicated) == []


def test_content_text_is_tagged_vietnamese(ontology_graph) -> None:
    untagged = sorted(
        f"{local(subject)}:{name}"
        for name in TEXT_PROPERTIES
        for subject, value in ontology_graph.subject_objects(A(name))
        if isinstance(value, Literal) and value.language != "vi"
    )

    assert untagged == []


def test_alternative_labels_are_names_not_ways_of_asking(ontology_graph) -> None:
    """Nhãn lỏng nghĩa sẽ được dùng làm biến thể bề mặt khi sinh dataset và dạy
    model trả lời sai một cách tự tin."""

    suspicious = sorted(
        f"{local(subject)}: {value}"
        for subject, value in ontology_graph.subject_objects(SKOS.altLabel)
        if re.search(
            r"\?|\bem\b|\btôi\b|làm sao|thế nào|ở đâu|là gì|cho ai|khi nào|ra sao"
            r"|bao nhiêu|gồm những gì",
            str(value),
            re.IGNORECASE,
        )
    )

    assert suspicious == []


def test_procedure_internal_nodes_are_never_named_by_a_user(ontology_graph) -> None:
    """Bước, điều kiện, thời hạn chỉ được hỏi thông qua quy trình chứa chúng, nên
    chúng phải luôn có một quy trình trỏ tới."""

    internal = {
        "ProcedureStep": "hasStep",
        "Requirement": "hasRequirement",
        "Deadline": "hasDeadline",
        "Outcome": "hasOutcome",
        "Consequence": "hasConsequence",
        "CaseResolution": "hasResolution",
    }
    detached = sorted(
        local(node)
        for class_name, relation in internal.items()
        for node in typed(ontology_graph, class_name)
        if not list(ontology_graph.subjects(A(relation), node))
    )

    assert detached == []


def test_every_procedure_says_what_it_is_and_how_to_do_it(ontology_graph) -> None:
    incomplete = sorted(
        local(procedure)
        for procedure in typed(ontology_graph, "AcademicProcedure")
        if not list(ontology_graph.objects(procedure, A("summaryText")))
        or not list(ontology_graph.objects(procedure, A("hasStep")))
    )

    assert incomplete == []


def test_a_document_part_belongs_to_a_document(ontology_graph) -> None:
    detached = sorted(
        local(node)
        for name in DOCUMENT_CLASSES
        for node in typed(ontology_graph, name)
        if not list(ontology_graph.objects(node, A("inDocument")))
    )

    assert detached == []


def test_the_old_regulation_is_quoted_only_where_the_new_one_is_silent(ontology_graph) -> None:
    """Quy chế 2021 chỉ được có mặt ở đúng Điều 10, không nhiều hơn.

    QĐ1052 thay thế QĐ753 ở mọi chỗ hai bản cùng nói - nó tự giới hạn phạm vi
    thay thế ở khoản 1 Điều 32: thay thế những gì "trái với" nó. Điều 10 của
    QĐ753 lọt lại vì QĐ1052 không có điều nào về việc sinh viên rút bớt học
    phần.

    Nạp thêm bất kỳ điều nào khác của QĐ753 là dựng hai đời của cùng một quy
    định cạnh nhau, và chatbot sẽ trả lời khác nhau tuỳ nó bắt trúng đời nào.
    Luật này đỏ ngay khi có người làm thế.
    """

    allowed = {
        "Regulation753Article10",
        "Regulation753Article10Clause01",
        "Regulation753Article10Clause02",
        "Regulation753Article10Clause03",
    }
    old = URIRef(ONTOLOGY_NS + "Regulation753")

    unexpected = sorted(
        local(node)
        for node in ontology_graph.subjects(A("inDocument"), old)
        if local(node) not in allowed
    )

    assert unexpected == []


def test_a_training_regulation_says_which_cohorts_it_governs(ontology_graph) -> None:
    """Quy chế đào tạo phải khai khoá áp dụng, vì đã có hơn một thế hệ.

    QĐ753 ghi "áp dụng cho khóa 60 trở đi", QĐ1052 ghi "khóa 64 trở đi". Thiếu
    trường này thì hai quy chế trông như nhau, và chatbot có thể dẫn nguồn từ
    bản đã bị thay cho một sinh viên thuộc khoá bản mới quản.

    Kiểm riêng quy chế đào tạo: quy chế tuyển sinh QĐ626 có hiệu lực từ ngày ký,
    không gắn với khoá; quyết định học phí hay học bổng cũng không gắn với khoá.
    """

    missing = sorted(
        local(node)
        for node in typed(ontology_graph, "Regulation")
        if "đào tạo" in str(next(ontology_graph.objects(node, A("title")), "")).casefold()
        if not list(ontology_graph.objects(node, A("minimumCohortNumber")))
    )

    assert missing == []


def test_ielts_and_toefl_columns_stay_in_the_source_table_order(ontology_graph) -> None:
    """Lỗi IELTS bị chặn ngay trên nguyên khối bảng, không qua node chép tay."""

    table = A("Regulation1052Appendix2Table03")
    text = str(next(ontology_graph.objects(table, A("verbatimTableText"))))

    assert "| TOEIC | IELTS | TOEFL iBT |" in text
    assert text.count("| ≥ 600 | ≥ 5.0 | ≥ 65 |") == 3
    assert text.count("| ≥ 700 | ≥ 5.5 | ≥ 70 |") == 3
    assert "| ≥ 600 | ≥ 65 | ≥ 5.0 |" not in text
    assert "| ≥ 700 | ≥ 70 | ≥ 5.5 |" not in text


def test_every_citation_is_readable(ontology_graph) -> None:
    missing = sorted(
        local(node)
        for name in DOCUMENT_CLASSES
        for node in typed(ontology_graph, name)
        if not any(
            getattr(value, "language", None) == "vi"
            for value in ontology_graph.objects(node, A("citationLabel"))
        )
    )

    assert missing == []
