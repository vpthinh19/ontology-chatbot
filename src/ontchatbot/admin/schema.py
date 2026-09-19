"""Lược đồ đọc từ shapes.ttl: mỗi loại thông tin có những ô nào.

Trang quản trị sinh form từ đây, và luật "ô nào phải gắn nguồn" cũng đọc từ đây. Các luật
còn lại - ô bắt buộc, số giá trị, kiểu dữ liệu, loại của mục được trỏ tới - do SHACL kiểm
khi ghi, nên form và bước kiểm không thể nói hai điều khác nhau.

Lược đồ cũng ghi ngược ra shapes.ttl (``to_turtle``) theo một thứ tự cố định: loại xếp theo
tên, ô xếp theo thuộc tính. Sửa một loại ở trang quản trị thì git diff chỉ đổi đúng chỗ đó.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pyoxigraph as oxi

from ..rdf import RDF, RDFS_LABEL, SH, SKOS_ALT_LABEL, XSD, local_id
from ..settings import ONTOLOGY_NS

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
#: Tên kiểu trong shapes.ttl của từng loại ô chữ/số.
_XSD_NAME = {"string": "string", "integer": "integer", "decimal": "decimal", "date": "date", "uri": "anyURI"}
KINDS = ("text", "string", "integer", "decimal", "date", "uri", "link", "choice")
_LANG_STRING = 'sh:datatype rdf:langString ; sh:languageIn ( "vi" )'
_PREAMBLE = """\
@prefix : <http://www.ntu.edu.vn/ontology/academic#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Cấu trúc ontology.trig khai báo bằng SHACL. Mỗi loại thông tin là một NodeShape: các
# ô nó có (sh:property), ô bắt buộc (sh:minCount 1), ô chỉ một giá trị (sh:maxCount 1),
# ô là chữ (sh:datatype), ô trỏ tới loại khác (sh:class) hay chọn trong danh sách cố
# định (sh:in). sh:closed cấm ô chưa khai báo. :batBuocNguon true nghĩa là câu của ô đó
# phải nằm trong một túi trích dẫn; false là được phép không nguồn (ô loại do ta tự đặt,
# cặp ghép mẫu đơn). Ô danh tính (nhãn, tên gọi khác) và tầng nguồn luôn nằm ngoài túi.

"""


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
    #: Bộ máy trích dẫn: không có ô nhãn, không hiện trên trang quản trị.
    internal: bool = False

    def field(self, property_name: str) -> Field | None:
        return next((field for field in self.fields if field.property == property_name), None)


def _literal(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    return f'"{escaped}"@vi'


def _block(lines: list[str]) -> str:
    return "\t\t" + " ;\n\t\t  ".join(lines) + " ]"


def _field_block(field: Field) -> str:
    lines = [f"[ sh:path :{field.property}", f"sh:name {_literal(field.name)}"]
    if field.kind == "text":
        lines.append(_LANG_STRING)
    elif field.kind == "link":
        lines.append(f"sh:class :{field.target}")
    elif field.kind == "choice":
        lines.append("sh:in ( " + " ".join(f":{choice}" for choice in field.choices) + " )")
    else:
        lines.append(f"sh:datatype xsd:{_XSD_NAME[field.kind]}")
    if field.required:
        lines.append("sh:minCount 1")
    if field.single:
        lines.append("sh:maxCount 1")
    if field.sourced is not None:
        lines.append(f":batBuocNguon {'true' if field.sourced else 'false'}")
    return _block(lines)


def _shape(spec: ClassSpec) -> str:
    blocks = []
    if not spec.internal:
        blocks.append(_block(["[ sh:path rdfs:label", 'sh:name "nhãn"@vi', _LANG_STRING, "sh:minCount 1", "sh:maxCount 1"]))
    if spec.alt_labels:
        blocks.append(_block(["[ sh:path skos:altLabel", 'sh:name "tên gọi khác"@vi', _LANG_STRING]))
    blocks += [_field_block(field) for field in sorted(spec.fields, key=lambda field: field.property)]
    return (
        f":{spec.name}Shape a sh:NodeShape ;\n"
        f"\tsh:targetClass :{spec.name} ;\n"
        f"\trdfs:label {_literal(spec.label)} ;\n"
        "\tsh:closed true ;\n"
        "\tsh:ignoredProperties ( rdf:type ) ;\n"
        "\tsh:property\n" + " ,\n".join(blocks) + " ."
    )


class Schema:
    def __init__(self, classes: dict[str, ClassSpec]) -> None:
        #: Mọi loại, kể cả bộ máy trích dẫn; ``classes`` chỉ gồm loại sửa được.
        self.all_classes = dict(sorted(classes.items()))
        self.classes = dict(sorted(((name, spec) for name, spec in classes.items() if not spec.internal),
                                   key=lambda item: item[1].label.casefold()))

    @classmethod
    def from_file(cls, path: Path | str) -> Schema:
        return cls.from_bytes(Path(path).read_bytes())

    @classmethod
    def from_bytes(cls, data: bytes) -> Schema:
        graph = oxi.Store()
        graph.load(data, format=oxi.RdfFormat.TURTLE)

        def objects(node, predicate: str) -> list:
            return [quad.object for quad in graph.quads_for_pattern(node, oxi.NamedNode(predicate), None, None)]

        def one(node, predicate: str):
            found = objects(node, predicate)
            return found[0] if found else None

        def members(head) -> list[str]:
            items = []
            while head is not None and head.value != RDF + "nil":
                items.append(local_id(one(head, RDF + "first").value))
                head = one(head, RDF + "rest")
            return items

        classes = {}
        for quad in graph.quads_for_pattern(None, oxi.NamedNode(SH + "targetClass"), None, None):
            name = local_id(quad.object.value)
            shape = quad.subject
            alt_labels = False
            fields = []
            for prop in objects(shape, SH + "property"):
                path = one(prop, SH + "path").value
                if path == RDFS_LABEL.value:
                    continue
                if path == SKOS_ALT_LABEL.value:
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
                    property=local_id(path),
                    name=label.value if label is not None else local_id(path),
                    kind=kind,
                    required=min_count is not None and int(min_count.value) > 0,
                    single=max_count is not None and int(max_count.value) == 1,
                    target=local_id(target.value) if target is not None else None,
                    choices=tuple(members(choices)) if choices is not None else (),
                    sourced=None if sourced is None else sourced.value == "true",
                ))
            fields.sort(key=lambda field: (not field.required, field.name))
            label = one(shape, RDFS_LABEL.value)
            classes[name] = ClassSpec(name, label.value if label is not None else name, alt_labels, tuple(fields),
                                      internal=name in INTERNAL_CLASSES)
        return cls(classes)

    def to_turtle(self) -> bytes:
        return (_PREAMBLE + "\n\n".join(_shape(spec) for spec in self.all_classes.values()) + "\n").encode("utf-8")

    # --- sửa lược đồ: mỗi hàm trả một lược đồ mới, lược đồ cũ giữ nguyên ---------

    def with_class(self, spec: ClassSpec, replacing: str | None = None) -> Schema:
        classes = {name: old for name, old in self.all_classes.items() if name != replacing}
        classes[spec.name] = spec
        if replacing and replacing != spec.name:
            classes = {name: replace(old, fields=tuple(
                replace(field, target=spec.name) if field.target == replacing else field for field in old.fields))
                for name, old in classes.items()}
        return Schema(classes)

    def without_class(self, name: str) -> Schema:
        return Schema({other: spec for other, spec in self.all_classes.items() if other != name})

    def renamed_property(self, old: str, new: str, name: str) -> Schema:
        """Đổi định danh (và tên hiển thị) của một thuộc tính ở mọi loại dùng nó."""

        return Schema({class_name: replace(spec, fields=tuple(
            replace(field, property=new, name=name) if field.property == old else field for field in spec.fields))
            for class_name, spec in self.all_classes.items()})

    def uses(self, property_name: str) -> list[str]:
        """Những loại có ô dùng thuộc tính này."""

        return [name for name, spec in self.all_classes.items() if spec.field(property_name)]

    def targeting(self, class_name: str) -> list[tuple[str, Field]]:
        """Những ô (ở loại khác) trỏ tới loại này."""

        return [(name, field) for name, spec in self.all_classes.items() if name != class_name
                for field in spec.fields if field.kind == "link" and field.target == class_name]
