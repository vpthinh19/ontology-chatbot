"""Build ontology v12 from v11 after the Stage B semantic review."""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import Graph, Literal, Namespace, RDF, RDFS
from rdflib.namespace import OWL, SKOS

ACADEMIC = Namespace("http://www.ntu.edu.vn/ontology/academic#")
ONTOLOGY_IRI = Namespace("http://www.ntu.edu.vn/ontology/").academic

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "resources/ontology/ontology_v11.ttl"
TARGET = ROOT / "resources/ontology/ontology_v12.ttl"
MANIFEST = ROOT / "resources/ontology/ontology_v11_to_v12.json"


def _vi(value: str) -> Literal:
    return Literal(value, lang="vi")


def _replace_literal(graph: Graph, subject: object, predicate: object, old: str, new: str) -> None:
    old_literal = _vi(old)
    if (subject, predicate, old_literal) not in graph:
        raise ValueError(f"missing value scheduled for replacement: {old}")
    graph.remove((subject, predicate, old_literal))
    graph.add((subject, predicate, _vi(new)))


def _add_new(graph: Graph, subject: object, predicate: object, value: object) -> None:
    if (subject, predicate, value) in graph:
        raise ValueError(f"value scheduled for addition already exists: {(subject, predicate, value)}")
    graph.add((subject, predicate, value))


def migrate(source: Path = SOURCE, target: Path = TARGET, manifest_path: Path = MANIFEST) -> dict:
    graph = Graph().parse(source, format="turtle")
    source_triples = len(graph)

    old_versions = list(graph.objects(ONTOLOGY_IRI, OWL.versionInfo))
    if old_versions != [Literal("11")]:
        raise ValueError(f"unexpected source version: {old_versions}")

    # Graduation conditions are atomic queryable values. The two legal and
    # disciplinary constraints are intentionally represented as one condition,
    # following the domain decision made during the Stage B review.
    _replace_literal(
        graph,
        ACADEMIC.GraduationReviewProcedure,
        ACADEMIC.condition,
        "Không bị truy cứu trách nhiệm hình sự",
        "Không bị truy cứu trách nhiệm hình sự và không bị kỷ luật",
    )
    for condition in (
        "Hoàn thành học phần Giáo dục quốc phòng và an ninh",
        "Hoàn thành học phần Giáo dục thể chất",
    ):
        _add_new(graph, ACADEMIC.GraduationReviewProcedure, ACADEMIC.condition, _vi(condition))

    _replace_literal(
        graph,
        ACADEMIC.GraduationReviewProcedure,
        ACADEMIC.content,
        """Sinh viên được xét tốt nghiệp khi không bị kỷ luật, tích lũy đủ số học phần, CPA >= 5.5, đạt chuẩn ngoại ngữ và hoàn thành GDQP-AN, GDTC.
Nếu đủ điều kiện sớm, có thể làm đơn xin xét tốt nghiệp sớm.""",
        """Sinh viên được xét tốt nghiệp khi hoàn thành nghĩa vụ đối với Trường; không bị truy cứu trách nhiệm hình sự và không bị kỷ luật; tích lũy đủ số tín chỉ; CPA từ 5.5 trở lên; đạt chuẩn năng lực tiếng Anh; hoàn thành Giáo dục quốc phòng và an ninh, Giáo dục thể chất.
Nếu đủ điều kiện sớm, sinh viên có thể làm đơn đề nghị xét tốt nghiệp.""",
    )

    scholarship_discipline = _vi("Không bị kỷ luật từ mức khiển trách trở lên")
    _add_new(
        graph,
        ACADEMIC.ScholarshipReviewProcedure,
        ACADEMIC.condition,
        scholarship_discipline,
    )
    _replace_literal(
        graph,
        ACADEMIC.ScholarshipReviewProcedure,
        ACADEMIC.outcome,
        "Nhận học bổng khuyến khích học tập nếu đủ điều kiện",
        "Được đưa vào danh sách xét học bổng; học bổng được cấp theo thứ tự kết quả học tập cho đến khi hết chỉ tiêu",
    )

    # Receiving a dossier and processing it are separate roles. Keeping two
    # explicit edges prevents the backend from guessing a role from prose.
    received_by = ACADEMIC.receivedBy
    for predicate, value in (
        (RDF.type, OWL.ObjectProperty),
        (RDFS.label, _vi("được tiếp nhận bởi")),
        (RDFS.domain, ACADEMIC.AcademicProcedure),
        (RDFS.range, ACADEMIC.AdministrativeOffice),
        (SKOS.altLabel, _vi("phòng tiếp nhận")),
        (SKOS.altLabel, _vi("nơi nhận hồ sơ")),
    ):
        _add_new(graph, received_by, predicate, value)
    _add_new(
        graph,
        ACADEMIC.MajorChangeProcedure,
        received_by,
        ACADEMIC.StudentAffairsOffice,
    )
    _replace_literal(
        graph,
        ACADEMIC.MajorChangeProcedure,
        ACADEMIC.content,
        """1. Sinh viên có nguyện vọng có thể được xem xét chuyển ngành trong cùng bậc học nếu không là sinh viên năm nhất/năm cuối và đạt điều kiện trúng tuyển.
2. Ít nhất 02 tuần trước khi bắt đầu học kỳ mới, SV làm đơn xin chuyển ngành để trình Hiệu trưởng thông qua Phòng Công tác Chính trị và Sinh viên xem xét quyết định.""",
        """1. Sinh viên có nguyện vọng có thể được xem xét chuyển ngành trong cùng bậc học nếu không là sinh viên năm nhất hoặc năm cuối và đạt điều kiện trúng tuyển.
2. Ít nhất 02 tuần trước khi bắt đầu học kỳ mới, sinh viên nộp đơn xin chuyển ngành tại Phòng Công tác Chính trị và Sinh viên. Phòng Đào tạo Đại học xử lý hồ sơ và trình Hiệu trưởng xem xét quyết định.""",
    )

    _replace_literal(
        graph,
        ACADEMIC.StudentAffairsOffice,
        RDFS.label,
        "Phòng Công tác Sinh viên",
        "Phòng Công tác Chính trị và Sinh viên",
    )
    for alias in ("Phòng Công tác Sinh viên", "Phòng CTCTSV", "CTCTSV"):
        _add_new(graph, ACADEMIC.StudentAffairsOffice, SKOS.altLabel, _vi(alias))

    graph.set((ONTOLOGY_IRI, OWL.versionInfo, Literal("12")))

    graph.bind("", ACADEMIC)
    graph.bind("owl", OWL)
    graph.bind("rdf", RDF)
    graph.bind("rdfs", RDFS)
    graph.bind("skos", SKOS)

    manifest = {
        "source": source.name,
        "target": target.name,
        "source_triples": source_triples,
        "target_triples": len(graph),
        "decisions": [
            {
                "issue": "graduation-conditions",
                "resolution": "Complete the structured condition list and combine the criminal and disciplinary constraints.",
            },
            {
                "issue": "scholarship-conditions",
                "resolution": "Add the disciplinary constraint to the structured condition list.",
            },
            {
                "issue": "scholarship-outcome",
                "resolution": "State that eligibility enters ranking and does not guarantee an award.",
            },
            {
                "issue": "major-change-office-roles",
                "resolution": "Student Affairs receives the dossier; Undergraduate Education processes it.",
            },
        ],
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(graph.serialize(format="turtle").rstrip() + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    manifest = migrate()
    print(
        f"created {manifest['target']}: "
        f"{manifest['source_triples']} -> {manifest['target_triples']} triples"
    )


if __name__ == "__main__":
    main()
