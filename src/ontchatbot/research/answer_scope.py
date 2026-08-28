"""Classify ontology individuals by their role in model-facing answers."""

from __future__ import annotations

from typing import Mapping

from rdflib import RDF, Graph, URIRef

from ..catalogue import QuerySpec
from .graph import execute_select


#: Các lớp của tầng văn bản.
#:
#: Chúng là neo trả lời được cho các câu hỏi về nguyên văn tài liệu.
SOURCE_CLASS_NAMES = frozenset(
    {
        "Chapter",
        "Article",
        "Clause",
        "Point",
        "Appendix",
        "DocumentTable",
        "CertificateConversionTable",
        "DocumentSection",
    }
)

#: Node nội bộ của một quy trình được hỏi thông qua quy trình chứa chúng, không
#: phải là neo của đường đi trả lời.
INTERNAL_CLASS_NAMES = frozenset(
    {
        "ProcedureStep",
        "Requirement",
        "Deadline",
        "Outcome",
        "Consequence",
        "CaseResolution",
    }
)

OPAQUE_RECORD_CLASS_NAMES = frozenset(
    {
        "PaymentFeeRule",
        "AcademicPerformanceBand",
        "GraduationClassificationBand",
        "StudyYearBand",
    }
)


def rdf_type_names(graph: Graph, node: URIRef) -> frozenset[str]:
    """Return local RDF type names for a project resource."""

    return frozenset(
        _local_name(value)
        for value in graph.objects(node, RDF.type)
        if isinstance(value, URIRef)
    )


def is_opaque_record(graph: Graph, node: URIRef) -> bool:
    """Whether a node is an internal storage record rather than a model slot."""

    return bool(rdf_type_names(graph, node) & OPAQUE_RECORD_CLASS_NAMES)


def _local_name(node: URIRef) -> str:
    value = str(node)
    return value.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


#: Họ truy vấn lấy toàn bộ dữ kiện của một thủ tục học vụ.
PROCEDURE_FAMILY = "academic-procedure-facts"


#: Dấu hiệu văn bản dùng để xác định dữ kiện mà một khuôn câu hỏi yêu cầu.
_SIGNER = ("ký quyết định", "hiệu trưởng")
_FEE = ("miễn phí", "chịu phí", "đồng mỗi lần", "phí 5.500")
_DURATION = ("nội dung thời hạn", "trong thời hạn", "trong vòng")
ANSWERED_BY: Mapping[str, tuple[str, ...]] = {
    # Người ký và người xét duyệt là hai vai trò khác nhau trong ontology.
    "{anchor} do ai ký duyệt": _SIGNER,
    "ai ký quyết định cho {anchor}": _SIGNER,
    "ai là người ký duyệt {anchor} năm nay": _SIGNER,
    # Dấu hiệu chi phí trong nội dung thủ tục.
    "{anchor} có mất phí không": _FEE,
    "{anchor} tốn bao nhiêu tiền": _FEE,
    "lệ phí làm {anchor} là bao nhiêu": _FEE,
    "{anchor} phải đóng thêm khoản nào không": _FEE,
    # Dấu hiệu người phụ trách trong nội dung thủ tục.
    "giảng viên nào phụ trách {anchor}": ("giảng viên",),
    # Dấu hiệu thời hạn; các trường hợp không đủ dữ kiện sẽ không được gán đáp án.
    "{anchor} mất bao nhiêu ngày mới được duyệt": _DURATION,
    "làm {anchor} mất bao lâu mới xong": _DURATION,
}


def dump_literals(
    graph: Graph, catalogue: Mapping[str, QuerySpec], family: str
) -> dict[str, str]:
    """Chạy truy vấn dump cho mọi neo của ``family``, gộp chữ trả về.

    Câu dump chỉ phụ thuộc neo, nên mỗi neo cần đúng một truy vấn.
    """

    spec = catalogue[family]
    slot = spec.slots["anchor"]
    values: dict[str, str] = {}
    for value in slot.values:
        query = spec.target_template.replace("${anchor}", value)
        rows = execute_select(graph, query)
        values[value[1:]] = " · ".join(
            str(cell) for row in rows for cell in row.values() if cell is not None
        ).casefold()
    return values


def answered_in_dump(dumped: str, template: str) -> bool:
    """Kết quả dump ``dumped`` có chứa dữ kiện mà ``template`` hỏi không?

    Khuôn không khai trong :data:`ANSWERED_BY` thì luôn trả ``False`` - nó hỏi
    thứ ontology không mô hình hoá, nên neo nào cũng hợp lệ.
    """

    return any(mark in dumped for mark in ANSWERED_BY.get(template, ()))
