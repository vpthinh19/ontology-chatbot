"""Sinh các dòng chỉ mục từ ontology."""

from __future__ import annotations

from ..rdf import compact
from .entries import EntryKind, IndexEntry
from .ontology import Ontology


class IndexBuilder:
    """Mỗi thực thể sinh ba loại dòng:

    - ``label``:             "<nhãn>", cho nhãn chính và mỗi tên gọi khác
    - ``datatype_property``: "<nhãn> | <tên thuộc tính>", mỗi thuộc tính một dòng
    - ``object_property``:   "<nhãn> | <tên thuộc tính> | <nhãn của đích>"

    Giá trị không vào chỉ mục; nội dung đến tay mô hình ở bước đọc hồ sơ.
    """

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology

    def build_entries(self) -> list[IndexEntry]:
        entries: dict[IndexEntry, None] = {}
        for node in self.ontology.individuals():
            entries.update(dict.fromkeys(self._entries_for(node)))
        return list(entries)

    def _entries_for(self, node: str) -> list[IndexEntry]:
        label = self.ontology.label(node)
        entries = [IndexEntry(EntryKind.LABEL, text, node) for text in self.ontology.labels(node)]
        datatype_names: set[str] = set()
        for assertion in self.ontology.assertions(node):
            if not self.ontology.policy.is_indexed(assertion.property):
                continue
            name = self.ontology.property_label(assertion.property)
            prop = compact(assertion.property)
            if assertion.target is not None:
                entries.append(IndexEntry(EntryKind.OBJECT_PROPERTY, f"{label} | {name} | {assertion.value}", node,
                                          property=prop, target=assertion.target))
            elif name not in datatype_names:
                datatype_names.add(name)
                entries.append(IndexEntry(EntryKind.DATATYPE_PROPERTY, f"{label} | {name}", node, property=prop))
        return entries
