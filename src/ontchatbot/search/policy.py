"""Thuộc tính nào vào chỉ mục, vào hồ sơ, và thực thể nào tra cứu được."""

from __future__ import annotations

from dataclasses import dataclass

from ..rdf import local_name


@dataclass(frozen=True)
class IndexPolicy:
    #: Tầng nguồn dùng để trích dẫn, không phải thứ người ta tra cứu.
    source_classes: frozenset[str] = frozenset({"Nguon", "DiaChiTrichDan"})
    #: Tiền tố của ô nói thực thể thuộc loại con nào, ví dụ ``loaiQuyTac``.
    type_property_prefix: str = "loai"
    #: Thuộc tính dựng nên trích dẫn chứ không phải dữ kiện: không vào hồ sơ lẫn chỉ mục.
    source_properties: frozenset[str] = frozenset({"thuocNguon", "toaDo"})
    #: Thuộc tính chỉ chứa địa chỉ: giá trị có trong hồ sơ, nhưng không ai tra theo tên chúng.
    unindexed_properties: frozenset[str] = frozenset({"diaChiTaiVe", "websiteDonVi", "hopThu"})

    def is_source_class(self, class_iri: str) -> bool:
        return local_name(class_iri) in self.source_classes

    def is_profile_fact(self, property_iri: str) -> bool:
        return local_name(property_iri) not in self.source_properties

    def is_indexed(self, property_iri: str) -> bool:
        name = local_name(property_iri)
        return name not in self.source_properties and name not in self.unindexed_properties
