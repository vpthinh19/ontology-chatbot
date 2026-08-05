"""Sinh bản nháp danh mục truy vấn từ danh mục khả năng trả lời.

``catalogue_validation`` bắt mọi mục ``supported`` phải được ít nhất một họ truy
vấn phủ. Viết tay 100+ họ vừa chậm vừa dễ sót, nên bản nháp được sinh cơ học từ
chính danh mục khả năng trả lời rồi mới chỉnh tay.

Hai loại neo được xử lý khác nhau:

* **neo gọi tên được** - quy trình, chính sách, biểu mẫu, ngành. Model sinh IRI
  của chúng, nên slot liệt kê giá trị hữu hạn.
* **bản ghi kỹ thuật** - mức học phí, quy tắc quy đổi chứng chỉ. Người dùng
  không gọi tên chúng, nên truy vấn ràng buộc theo lớp và để backend tìm bằng
  điều kiện nghiệp vụ; không có slot IRI nào cả.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from rdflib import URIRef

from ..settings import ANSWER_INVENTORY_PATH, ONTOLOGY_NS, QUERY_CATALOGUE_PATH
from ..runtime.sparql import load_ontology
from .answer_scope import is_opaque_record, rdf_type_names

#: Lớp neo -> miền của họ truy vấn, dùng cho báo cáo độ phủ.
DOMAIN_OF_CLASS = {
    "AcademicProcedure": "procedure",
    "AcademicPolicy": "academic-rule",
    "AcademicProgram": "tuition",
    "DisciplineGroup": "tuition",
    "TuitionRate": "tuition",
    "DoctoralTuitionDurationRule": "tuition",
    "PaymentMethod": "tuition",
    "PaymentFeeRule": "tuition",
    "Bank": "tuition",
    "BillingUnit": "tuition",
    "Certificate": "certificate",
    "LanguageCertificate": "certificate",
    "ComputerCertificate": "certificate",
    "CertificateConversionRule": "certificate",
    "LanguageCompetencyLevel": "certificate",
    "CourseExemption": "certificate",
    "LearnerCategory": "certificate",
    "FormDocument": "form",
    "FormCatalogue": "form",
    "FormCatalogueEntry": "form",
}
DEFAULT_DOMAIN = "academic-rule"
_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def _kebab(name: str) -> str:
    return _CAMEL.sub("-", name.replace("rdfs:label", "Label")).lower()


def _primary_class(classes: tuple[str, ...]) -> str:
    """Lớp cụ thể nhất: lớp con luôn đứng sau lớp cha trong dữ liệu dự án."""

    for preferred in (
        "AcademicProcedure", "AcademicPolicy", "CertificateConversionRule",
        "TuitionRate", "FormCatalogueEntry", "FormDocument", "AcademicProgram",
    ):
        if preferred in classes:
            return preferred
    return classes[0] if classes else "Thing"


def _template(path: tuple[str, ...], *, anchored: bool, anchor_class: str) -> str:
    """Dựng một truy vấn một dòng đi theo đúng đường đi đã khai.

    Neo gọi tên được thì đứng thẳng làm chủ thể. Bản ghi kỹ thuật thì ràng buộc
    theo lớp và để một biến làm chủ thể - model không phải học IRI của chúng.
    """

    if anchored:
        steps, cursor = [], "${anchor}"
    else:
        steps, cursor = [f"?item a :{anchor_class} ."], "?item"
    for index, component in enumerate(path):
        predicate = "rdfs:label" if component == "rdfs:label" else f":{component}"
        target = "?answer" if index == len(path) - 1 else "?node"
        steps.append(f"{cursor} {predicate} {target} .")
        cursor = target
    return f"SELECT DISTINCT ?answer WHERE {{ {' '.join(steps)} }}"


def build(inventory_path: Path = ANSWER_INVENTORY_PATH) -> list[dict[str, object]]:
    graph = load_ontology()
    entries = json.loads(Path(inventory_path).read_text(encoding="utf-8"))["entries"]
    groups: dict[tuple[tuple[str, ...], tuple[str, ...]], list[str]] = defaultdict(list)
    for entry in entries:
        if entry["status"] != "supported":
            continue
        node = URIRef(ONTOLOGY_NS + entry["anchor"])
        classes = tuple(sorted(rdf_type_names(graph, node) - {"NamedIndividual"}))
        groups[(classes, tuple(entry["path"]))].append(entry["anchor"])

    families: list[dict[str, object]] = []
    used: set[str] = set()
    for (classes, path), anchors in sorted(groups.items()):
        anchor_class = _primary_class(classes)
        opaque = is_opaque_record(graph, URIRef(ONTOLOGY_NS + anchors[0]))
        query_id = "-".join([_kebab(anchor_class), *(_kebab(p) for p in path)])
        suffix = 2
        while query_id in used:
            query_id = f"{query_id}-{suffix}"
            suffix += 1
        used.add(query_id)

        template = _template(path, anchored=not opaque, anchor_class=anchor_class)
        slots: dict[str, object] = (
            {}
            if opaque
            else {"anchor": {"kind": "iri", "values": [f":{a}" for a in sorted(anchors)]}}
        )
        families.append(
            {
                "query_id": query_id,
                "domain": DOMAIN_OF_CLASS.get(anchor_class, DEFAULT_DOMAIN),
                "target_template": template,
                "slots": slots,
                "coverage": [
                    {"anchor_classes": [anchor_class], "paths": [list(path)]}
                ],
            }
        )
    return families


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=QUERY_CATALOGUE_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    families = build()
    Path(args.output).write_text(
        "".join(
            json.dumps(family, ensure_ascii=False, separators=(",", ":")) + "\n"
            for family in families
        )
        + json.dumps(
            {
                "query_id": "no-information",
                "domain": "out-of-domain",
                "target_template": "không có thông tin",
                "slots": {},
                "coverage": [],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    anchored = sum(1 for family in families if family["slots"])
    print(
        f"{len(families) + 1} họ truy vấn "
        f"({anchored} có slot IRI, {len(families) - anchored} ràng buộc theo lớp) "
        f"-> {args.output}"
    )


if __name__ == "__main__":
    main()
