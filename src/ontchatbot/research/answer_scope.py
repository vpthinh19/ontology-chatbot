"""Classify ontology individuals by their role in model-facing answers."""

from __future__ import annotations

from rdflib import RDF, Graph, URIRef


#: Các lớp của tầng văn bản.
#:
#: Chúng LÀ neo trả lời được: "Điều 24 nói gì" là câu hỏi hợp lệ và người dùng
#: không cần đi vòng qua một dữ kiện nghiệp vụ để hỏi nó. Bản trước loại tầng
#: này khỏi danh sách neo, khiến 60% nguyên văn công văn nằm chết trong đồ thị.
SOURCE_CLASS_NAMES = frozenset(
    {
        "Chapter",
        "Article",
        "Clause",
        "Point",
        "Appendix",
        "DocumentTable",
        "DocumentSection",
    }
)

#: Node nội bộ của một quy trình: nội dung của chúng chỉ được hỏi thông qua quy
#: trình chứa chúng, nên chúng không bao giờ là neo của một đường đi trả lời.
#: Khác với bản ghi kỹ thuật bên dưới - bản ghi vẫn là neo vì SPARQL tìm tới
#: chúng bằng điều kiện nghiệp vụ.
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
        "CertificateConversionRule",
        "TuitionRate",
        "PaymentFeeRule",
        "AcademicPerformanceBand",
        "GraduationClassificationBand",
        "StudyYearBand",
        "DoctoralTuitionDurationRule",
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
