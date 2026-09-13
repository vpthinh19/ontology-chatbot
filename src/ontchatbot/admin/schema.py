"""Lược đồ đọc từ shapes.ttl: mỗi loại thông tin có những ô nào.

Trang quản trị sinh form từ đây, và luật "ô nào phải gắn nguồn" cũng đọc từ đây. Các luật
còn lại - ô bắt buộc, số giá trị, kiểu dữ liệu, loại của mục được trỏ tới - do SHACL kiểm
khi ghi, nên form và bước kiểm không thể nói hai điều khác nhau.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyoxigraph as oxi

from ..settings import ONTOLOGY_NS

SH = "http://www.w3.org/ns/shacl#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XSD = "http://www.w3.org/2001/XMLSchema#"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
SKOS_ALT_LABEL = "http://www.w3.org/2004/02/skos/core#altLabel"
#: Loại chỉ là bộ máy trích dẫn: được tạo và dọn tự động, không sửa tay.
INTERNAL_CLASSES = frozenset({"DiaChiTrichDan"})
KIND_BY_DATATYPE = {
    RDF + "langString": "text",
    XSD + "string": "string",
    XSD + "integer": "integer",
    XSD + "decimal": "decimal",
    XSD + "date": "date",
    XSD + "anyURI": "uri",
}


@dataclass(frozen=True)
class Field:
    """Một ô của form."""

    property: str
    name: str
    #: text · string · integer · decimal · date · uri · link (trỏ tới mục) · choice (chọn trong danh sách)
    kind: str
    required: bool
    single: bool
    target: str | None = None
    choices: tuple[str, ...] = ()
    #: True: phải gắn nguồn · False: gắn hay không đều được · None: không gắn nguồn (tầng nguồn)
    sourced: bool | None = None


@dataclass(frozen=True)
class ClassSpec:
    name: str
    label: str
    alt_labels: bool
    fields: tuple[Field, ...]

    def field(self, property_name: str) -> Field | None:
        return next((field for field in self.fields if field.property == property_name), None)


def _local(value: str) -> str:
    return value[len(ONTOLOGY_NS):] if value.startswith(ONTOLOGY_NS) else value


class Schema:
    def __init__(self, classes: dict[str, ClassSpec]) -> None:
        self.classes = classes

    @classmethod
    def from_file(cls, path: Path | str) -> Schema:
        graph = oxi.Store()
        graph.load(path=str(path), format=oxi.RdfFormat.TURTLE)

        def objects(node, predicate: str) -> list:
            return [quad.object for quad in graph.quads_for_pattern(node, oxi.NamedNode(predicate), None, None)]

        def one(node, predicate: str):
            found = objects(node, predicate)
            return found[0] if found else None

        def members(head) -> list[str]:
            items = []
            while head is not None and head.value != RDF + "nil":
                items.append(_local(one(head, RDF + "first").value))
                head = one(head, RDF + "rest")
            return items

        classes = {}
        for quad in graph.quads_for_pattern(None, oxi.NamedNode(SH + "targetClass"), None, None):
            name = _local(quad.object.value)
            if name in INTERNAL_CLASSES:
                continue
            shape = quad.subject
            alt_labels = False
            fields = []
            for prop in objects(shape, SH + "property"):
                path = one(prop, SH + "path").value
                if path == RDFS_LABEL:
                    continue
                if path == SKOS_ALT_LABEL:
                    alt_labels = True
                    continue
                target, choices, datatype = one(prop, SH + "class"), one(prop, SH + "in"), one(prop, SH + "datatype")
                if target is not None:
                    kind = "link"
                elif choices is not None:
                    kind = "choice"
                else:
                    kind = KIND_BY_DATATYPE.get(datatype.value if datatype is not None else "", "string")
                min_count, max_count = one(prop, SH + "minCount"), one(prop, SH + "maxCount")
                sourced = one(prop, ONTOLOGY_NS + "batBuocNguon")
                label = one(prop, SH + "name")
                fields.append(Field(
                    property=_local(path),
                    name=label.value if label is not None else _local(path),
                    kind=kind,
                    required=min_count is not None and int(min_count.value) > 0,
                    single=max_count is not None and int(max_count.value) == 1,
                    target=_local(target.value) if target is not None else None,
                    choices=tuple(members(choices)) if choices is not None else (),
                    sourced=None if sourced is None else sourced.value == "true",
                ))
            fields.sort(key=lambda field: (not field.required, field.name))
            label = one(shape, RDFS_LABEL)
            classes[name] = ClassSpec(name, label.value if label is not None else name, alt_labels, tuple(fields))
        return cls(dict(sorted(classes.items(), key=lambda item: item[1].label.casefold())))
