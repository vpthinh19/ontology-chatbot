"""Hồ sơ của một thực thể: mọi dữ kiện, gom theo nguồn đã khẳng định chúng."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..rdf import local_name
from .ontology import Ontology


@dataclass(frozen=True)
class Source:
    """Trích dẫn đầy đủ của một túi: toạ độ cộng thông tin của nguồn."""

    citation: str
    url: str | None = None


@dataclass(frozen=True)
class Fact:
    """Một câu về thực thể, hoặc câu của thực thể khác nói tới nó."""

    subject_label: str
    property_label: str
    value: str
    target: str | None = None


@dataclass
class NodeProfile:
    node: str
    label: str
    classes: list[str]
    #: Mỗi nhóm là (nguồn, các dữ kiện); nguồn ``None`` là không trích dẫn được.
    groups: list[tuple[Source | None, list[Fact]]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "label": self.label,
            "classes": self.classes,
            "groups": [
                {
                    "citation": source.citation if source else None,
                    "url": source.url if source else None,
                    "facts": [
                        {"about": fact.subject_label, "property": fact.property_label,
                         "value": fact.value, "target": fact.target}
                        for fact in facts
                    ],
                }
                for source, facts in self.groups
            ],
        }


class ProfileReader:
    """Đọc hồ sơ và dựng chuỗi trích dẫn. Trích dẫn của mỗi túi được ghép một lần rồi nhớ lại."""

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology
        self._sources: dict[str, Source | None] = {}

    def source(self, bag: str | None) -> Source | None:
        if bag is None:
            return None
        if bag not in self._sources:
            self._sources[bag] = self._cite(bag)
        return self._sources[bag]

    def _cite(self, bag: str) -> Source | None:
        ontology = self.ontology
        parts: dict = {}
        for assertion in ontology.assertions_raw(bag):
            parts.setdefault(local_name(assertion.property), assertion)
        origin = parts["thuocNguon"].target if "thuocNguon" in parts else None
        if origin is None:
            return None
        coordinate = parts["toaDo"].value if "toaDo" in parts else ""
        info = {local_name(a.property): a.value for a in ontology.assertions_raw(origin)}
        pieces = [f"{coordinate} {ontology.label(origin)}".strip()]
        if info.get("soHieu"):
            issued = _vietnamese_date(info.get("banHanhNgay"))
            pieces.append(f"ban hành kèm Quyết định {info['soHieu']}" + (f" ngày {issued}" if issued else ""))
        elif info.get("ngayThuThap"):
            pieces.append(f"truy cập ngày {_vietnamese_date(info['ngayThuThap'])}")
        return Source(", ".join(piece for piece in pieces if piece), info.get("duongDan"))

    def read(self, node: str) -> NodeProfile:
        by_bag: dict[str | None, list[Fact]] = {}
        label = self.ontology.label(node)
        for assertion in self.ontology.assertions(node):
            by_bag.setdefault(assertion.bag, []).append(
                Fact(label, self.ontology.property_label(assertion.property), assertion.value, assertion.target))
        for subject, assertion in self.ontology.incoming(node):
            by_bag.setdefault(assertion.bag, []).append(
                Fact(self.ontology.label(subject), self.ontology.property_label(assertion.property),
                     assertion.value, assertion.target))
        groups = [(self.source(bag), facts) for bag, facts in by_bag.items()]
        # Nhóm nhiều dữ kiện trước; nhóm không nguồn xuống cuối để mô hình không trích dẫn nhầm.
        groups.sort(key=lambda group: (group[0] is None, -len(group[1])))
        return NodeProfile(node, label, self.ontology.class_labels(node), groups)


def _vietnamese_date(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        year, month, day = iso.split("-")
        return f"{int(day)}/{int(month)}/{year}"
    except ValueError:
        return iso
