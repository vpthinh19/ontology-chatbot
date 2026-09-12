"""Quét ontology để sinh các dòng chỉ mục."""

from __future__ import annotations

from .entries import EntryKind, IndexEntry
from .ontology import Ontology
from .vocabulary import compact


class IndexBuilder:
    """Sinh ba loại dòng cho mỗi thực thể:

    - ``label``:             "<nhãn>" cho nhãn chính và mỗi tên gọi phụ
    - ``datatype_property``: "<nhãn> | <tên thuộc tính>", mỗi thuộc tính một dòng
    - ``object_property``:   "<nhãn> | <tên thuộc tính> | <nhãn của đích>"

    Giá trị không vào dòng chỉ mục: người ta hỏi "học phí ngành nào", không hỏi
    theo con số. Nội dung đến tay mô hình ở bước đọc hồ sơ.
    """

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology

    def build_entries(self) -> list[IndexEntry]:
        entries: dict[tuple, IndexEntry] = {}
        for node in self.ontology.individuals():
            for entry in self._entries_for(node):
                entries.setdefault((entry.kind, entry.text, entry.node, entry.property, entry.target), entry)
        return list(entries.values())

    def _entries_for(self, node: str) -> list[IndexEntry]:
        nhan = self.ontology.label(node)
        ra = [IndexEntry(EntryKind.LABEL, text, node) for text in self.ontology.labels(node)]
        da_co: set[str] = set()
        for a in self.ontology.assertions(node):
            if not self.ontology.policy.is_indexed(a.property):
                continue
            ten = self.ontology.property_label(a.property)
            if a.target is None:
                if ten in da_co:
                    continue
                da_co.add(ten)
                ra.append(IndexEntry(EntryKind.DATATYPE_PROPERTY, f"{nhan} | {ten}", node,
                                     property=compact(a.property)))
            else:
                ra.append(IndexEntry(EntryKind.OBJECT_PROPERTY, f"{nhan} | {ten} | {a.value}", node,
                                     property=compact(a.property), target=a.target))
        return ra
