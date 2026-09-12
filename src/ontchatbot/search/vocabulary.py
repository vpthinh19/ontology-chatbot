"""Tên gọi thành phần ontology và chính sách đưa thuộc tính vào chỉ mục."""

from __future__ import annotations

from dataclasses import dataclass

from ..settings import ONTOLOGY_NS


def local_name(iri: str) -> str:
    """Phần sau dấu # của IRI, ví dụ ``nopTai``."""

    text = str(iri)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rsplit("/", 1)[-1]


def compact(iri: str) -> str:
    """IRI trong namespace học vụ viết gọn thành ``:TenCucBo``; IRI khác giữ nguyên."""

    text = str(iri)
    return ":" + text[len(ONTOLOGY_NS):] if text.startswith(ONTOLOGY_NS) else text


def expand(text: str) -> str:
    """Ngược lại của ``compact``."""

    return ONTOLOGY_NS + text[1:] if text.startswith(":") else text


@dataclass(frozen=True)
class IndexPolicy:
    """Quyết định thuộc tính nào vào chỉ mục và thực thể nào tra cứu được.

    Mọi quyết định mang tính "biên soạn" nằm ở đây, tách khỏi thuật toán.
    """

    #: Địa chỉ trích dẫn là bộ máy dẫn nguồn thuần tuý: không ai hỏi "khoản 3 Điều 24"
    #: như một thực thể. Nguồn thô thì KHÁC - "trang tra cứu học phí", "danh mục biểu
    #: mẫu", "thông báo học bổng" đều là thứ người ta hỏi tới, nên vẫn tra cứu được.
    source_classes: frozenset[str] = frozenset({"DiaChiTrichDan"})
    #: Tiền tố của ô nói rõ thực thể thuộc loại con nào, ví dụ ``loaiQuyTac``.
    type_property_prefix: str = "loai"
    #: Thuộc tính nối một câu với địa chỉ trích dẫn của nó. Chúng dựng nên trích dẫn
    #: chứ không phải dữ kiện, nên không vào hồ sơ lẫn chỉ mục.
    source_properties: frozenset[str] = frozenset({"thuocNguon", "toaDo"})
    #: Đường dẫn tải: người hỏi cần giá trị, nhưng không ai hỏi "cái gì có đường dẫn".
    unindexed_properties: frozenset[str] = frozenset({"diaChiTaiVe", "websiteDonVi", "hopThu"})

    def is_source_class(self, class_iri: str) -> bool:
        return local_name(class_iri) in self.source_classes

    def is_profile_fact(self, property_iri: str) -> bool:
        """Câu đáng đưa vào hồ sơ trả cho mô hình."""

        return local_name(property_iri) not in self.source_properties

    def is_indexed(self, property_iri: str) -> bool:
        """Câu đáng sinh một dòng chỉ mục để tìm kiếm."""

        name = local_name(property_iri)
        return name not in self.source_properties and name not in self.unindexed_properties
