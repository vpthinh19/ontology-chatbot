"""Hồ sơ của một thực thể: mọi dữ kiện, gom theo nguồn đã khẳng định chúng.

Nguồn không phải đi tìm. Mỗi câu ba phần nằm sẵn trong một cái túi, tên túi là địa
chỉ trích dẫn, nên đọc hồ sơ chỉ là quét các câu rồi gom theo túi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ontology import Assertion, Ontology
from .vocabulary import local_name


@dataclass(frozen=True)
class Source:
    """Trích dẫn đầy đủ của một cái túi, ghép từ toạ độ và thông tin nguồn thô."""

    citation: str
    url: str | None = None


@dataclass(frozen=True)
class Fact:
    """Một phát biểu về thực thể, hoặc một phát biểu của thực thể khác về nó."""

    subject_label: str
    property_label: str
    value: str
    target: str | None = None


@dataclass
class NodeProfile:
    node: str
    label: str
    classes: list[str]
    #: Mỗi nhóm là (nguồn, các dữ kiện). Nguồn ``None`` nghĩa là không trích dẫn được.
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
    """Đọc hồ sơ và dựng chuỗi trích dẫn. Trích dẫn được nhớ lại vì mỗi túi chỉ
    cần ghép chuỗi một lần cho cả vòng đời tiến trình."""

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology
        self._nho: dict[str, Source | None] = {}

    def source(self, bag: str | None) -> Source | None:
        """Trích dẫn của một cái túi: toạ độ cộng thông tin của nguồn thô."""

        if bag is None:
            return None
        if bag in self._nho:
            return self._nho[bag]

        ont = self.ontology
        toa_do = next((a.value for a in ont.assertions_raw(bag) if local_name(a.property) == "toaDo"), "")
        nguon = next((a.target for a in ont.assertions_raw(bag) if local_name(a.property) == "thuocNguon"), None)
        if nguon is None:
            self._nho[bag] = None
            return None

        o = {local_name(a.property): a.value for a in ont.assertions_raw(nguon)}
        phan = [f"{toa_do} {ont.label(nguon)}".strip()]
        if o.get("soHieu"):
            ngay = _ngay_viet(o.get("banHanhNgay"))
            phan.append(f"ban hành kèm Quyết định {o['soHieu']}" + (f" ngày {ngay}" if ngay else ""))
        elif o.get("ngayThuThap"):
            phan.append(f"truy cập ngày {_ngay_viet(o['ngayThuThap'])}")
        source = Source(", ".join(p for p in phan if p), o.get("duongDan"))
        self._nho[bag] = source
        return source

    def read(self, node: str) -> NodeProfile:
        theo_tui: dict[str | None, list[Fact]] = {}
        nhan = self.ontology.label(node)

        for a in self.ontology.assertions(node):
            theo_tui.setdefault(a.bag, []).append(
                Fact(nhan, self.ontology.property_label(a.property), a.value, a.target))

        for chu_the, a in self.ontology.incoming(node):
            theo_tui.setdefault(a.bag, []).append(
                Fact(self.ontology.label(chu_the), self.ontology.property_label(a.property),
                     a.value, a.target))

        nhom = [(self.source(bag), facts) for bag, facts in theo_tui.items()]
        # Nhóm nhiều dữ kiện nhất đứng trước; nhóm không có nguồn xuống cuối để mô
        # hình không lỡ trích dẫn cho những câu ta tự khẳng định.
        nhom.sort(key=lambda x: (x[0] is None, -len(x[1])))
        return NodeProfile(node, nhan, self.ontology.class_labels(node), nhom)


def _ngay_viet(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        nam, thang, ngay = iso.split("-")
        return f"{int(ngay)}/{int(thang)}/{nam}"
    except ValueError:
        return iso
