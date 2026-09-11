"""Tên gọi thành phần ontology và chính sách đưa thuộc tính vào chỉ mục."""

from __future__ import annotations

from dataclasses import dataclass

from rdflib import Namespace, URIRef

from ..settings import ONTOLOGY_NS

ACADEMIC = Namespace(ONTOLOGY_NS)


def local_name(iri: URIRef | str) -> str:
    """Phần sau dấu # của IRI, ví dụ ``submittedTo``."""

    text = str(iri)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rsplit("/", 1)[-1]


def compact(iri: URIRef | str) -> str:
    """IRI trong namespace học vụ viết gọn thành ``:TenCucBo``; IRI khác giữ nguyên."""

    text = str(iri)
    return ":" + text[len(ACADEMIC):] if text.startswith(str(ACADEMIC)) else text


def expand(text: str) -> URIRef:
    """Ngược lại của ``compact``."""

    return URIRef(str(ACADEMIC) + text[1:]) if text.startswith(":") else URIRef(text)


@dataclass(frozen=True)
class IndexPolicy:
    """Quyết định thuộc tính nào vào chỉ mục, vào hồ sơ, hay dùng làm nguồn.

    Mọi quyết định mang tính "biên soạn" nằm ở đây, tách khỏi thuật toán. Sau này
    có thể đọc các tập này từ chú thích trong chính ontology.
    """

    #: object_property nối một node nghiệp vụ tới phần văn bản làm căn cứ.
    source_property: str = "basedOn"
    #: datatype_property chứa trích dẫn của phần văn bản làm căn cứ.
    citation_property: str = "citationLabel"
    #: datatype_property chứa đường dẫn của nguồn, xét theo thứ tự.
    url_properties: tuple[str, ...] = ("documentUrl", "webPageUrl")
    #: object_property mà đích là thành phần của chủ thể: bước, điều kiện...
    component_properties: frozenset[str] = frozenset(
        {"hasStep", "hasRequirement", "hasDeadline", "hasOutcome", "hasConsequence", "hasResolution"}
    )
    #: datatype_property dùng để sắp thứ tự các thành phần.
    order_properties: tuple[str, ...] = ("stepOrder", "requirementOrder")
    #: Thuộc tính kỹ thuật: không sinh dòng chỉ mục, vì người hỏi không hỏi theo chúng.
    unindexed_properties: frozenset[str] = frozenset(
        {
            "basedOn", "citationLabel", "documentUrl", "webPageUrl", "retrievedDate",
            "partOf", "inDocument",
            "articleNumber", "clauseNumber", "pointLetter", "chapterNumber", "appendixNumber",
            "stepOrder", "requirementOrder",
        }
    )

    def is_indexed(self, property_iri: URIRef | str) -> bool:
        return local_name(property_iri) not in self.unindexed_properties

    def is_component(self, property_iri: URIRef | str) -> bool:
        return local_name(property_iri) in self.component_properties

    def is_profile_fact(self, property_iri: URIRef | str) -> bool:
        """Căn cứ và trích dẫn biến thành nguồn của dữ kiện, không phải dữ kiện."""

        return local_name(property_iri) not in {self.source_property, self.citation_property}
