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

from ..settings import (
    ANSWER_INVENTORY_PATH,
    ONTOLOGY_NS,
    QUERY_CATALOGUE_MANUAL_PATH,
    QUERY_CATALOGUE_PATH,
)
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
    # Tầng văn bản: tra cứu nguyên văn theo số hiệu điều khoản.
    "Decision": "document",
    "Regulation": "document",
    "GuidanceDocument": "document",
    "Chapter": "document",
    "Article": "document",
    "Clause": "document",
    "Point": "document",
    "Appendix": "document",
    "DocumentTable": "document",
    "DocumentSection": "document",
}
DEFAULT_DOMAIN = "academic-rule"
_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")

#: Hai đường đi tới trích dẫn. Chúng KHÔNG sinh họ riêng cho từng lớp neo.
#:
#: Người hỏi "cái này căn cứ vào đâu" luôn muốn đúng một thứ - tên điều khoản kèm
#: đường dẫn bản gốc - bất kể đang hỏi về chứng chỉ, học phí hay một quy tắc. Tách
#: thành ~90 họ gần giống hệt nhau không thêm năng lực nào, mà làm model lẫn khi
#: chọn họ: đó chính là chế độ lỗi đã đo được (nhận đúng thực thể, sai quan hệ).
#: Một họ gộp trả cả hai cột cùng lúc, đúng nguyên tắc "nội dung kèm nguồn" mà các
#: họ ``*-with-source`` viết tay đã theo.
CITATION_PATHS = (("basedOn", "citationLabel"), ("basedOn", "documentUrl"))
CITATION_QUERY_ID = "source-citation"

#: Lớp của tầng văn bản, dùng để nhận ra câu hỏi vòng tròn bên dưới.
_DOCUMENT_PART_CLASSES = frozenset(
    {"Chapter", "Article", "Clause", "Point", "Appendix", "DocumentTable", "DocumentSection"}
)
#: Số hiệu định vị. Hỏi chúng trên chính phần văn bản vừa được gọi tên là hỏi
#: vòng tròn: "khoản 3 Điều 24 thuộc điều số mấy" đã có câu trả lời trong câu hỏi.
_LOCATOR_TERMINALS = frozenset(
    {"articleNumber", "clauseNumber", "pointLetter", "chapterNumber", "appendixNumber"}
)
#: Cờ boolean của bảng ngưỡng: dữ liệu nội bộ để so sánh, không phải câu trả lời.
_INTERNAL_FLAG_TERMINALS = frozenset({"minimumInclusive", "maximumInclusive"})
#: Cột ngưỡng số của bảng phân loại. Người dùng hỏi chúng bằng MỘT GIÁ TRỊ ("7,5
#: điểm xếp loại gì") qua họ viết tay, không bao giờ hỏi "liệt kê mọi ngưỡng dưới".
_THRESHOLD_TERMINALS = frozenset(
    {
        "minimumValue", "maximumValue",
        "minimumScore", "maximumScore",
        "minimumCredits", "maximumCredits",
        "minimumPercentage", "maximumPercentage",
    }
)
#: Quan hệ chỉ dùng để đi ngược cây cấu trúc văn bản.
_STRUCTURAL_RELATIONS = frozenset({"inDocument", "partOf"})


#: Họ mà CÂU HỎI của nó trùng với một họ khác, dù truy vấn khác nhau.
#:
#: Đo được từ hai lượt huấn luyện: model nhầm ``class-size-rule`` với
#: ``class-size-rule-maximum-value`` **17 lần** - nhiều nhất trong 83 cặp bị
#: nhầm. Đọc câu chấm thật thì rõ vì sao: *"quy mô lớp X giới hạn bao nhiêu sinh
#: viên"* và *"sĩ số tối đa của quy mô lớp X"* là **cùng một câu hỏi**, mà dataset
#: bắt model chọn hai đích khác nhau rồi chấm sai khi nó đoán nhầm.
#:
#: Họ cha ``class-size-rule`` (viết tay) trả về cả dòng quy tắc - đã kiểm chứng
#: là chứa đúng giá trị mà hai họ con trả riêng. ``criterion-text`` thì chép lại
#: chính hai con số đó dưới dạng câu văn.
#:
#: Hạ xuống secondary chứ KHÔNG xoá: chúng vẫn chạy được ở runtime và vẫn phủ
#: answer inventory, chỉ thôi cạnh tranh với họ cha khi dạy.
_QUESTION_DUPLICATES = frozenset(
    {
        # Họ cha ``class-size-rule`` trả cả dòng quy tắc, đã kiểm chứng là chứa
        # đúng giá trị hai họ con trả riêng.
        "class-size-rule-maximum-value",
        "class-size-rule-minimum-value",
        "class-size-rule-criterion-text",
        # Người dùng: "không ai hỏi tiêu đề cả". Với một văn bản thì "tên" và
        # "tiêu đề" là một thứ trong đầu người hỏi; model nhầm 13 lần.
        "document-title",
        # Người dùng: hỏi biểu mẫu thì "chỉ cần trả về link tải là đủ, vì hầu hết
        # thông tin của biểu mẫu nằm trong file tải qua link". Họ ``form-download``
        # trả tên + số hiệu + link cùng lúc.
        "form-catalogue-entry-listed-title",
        "form-catalogue-entry-listed-form-number",
        "form-catalogue-entry-download-url",
        "form-catalogue-entry-catalogue-entry-for-form-label",
        # Người dùng: mô tả trường hợp và cách giải quyết "rất giống nhau, có khả
        # năng thay thế cho nhau trong cùng một câu nói". ``academic-case-details``
        # trả cả hai.
        "academic-case-case-text",
        "academic-case-has-resolution-condition-text",
        # Người dùng: tên thủ tục kế tiếp và mô tả của nó "rất giống nhau, có thể
        # xem như một". ``academic-procedure-next-procedure-details`` trả cả hai.
        "academic-procedure-next-procedure-label",
        "academic-procedure-next-procedure-summary-text",
        # Người dùng: "chatbot nhỏ nên không cần trả lời quá ngắn như tên, mà nên
        # trả về thông tin có giá trị. Trả về thông tin ngắn chỉ có ý nghĩa nếu
        # có LLM đứng sau đọc hộ." Năm nhóm dưới đây đều trả một mẩu rời của cùng
        # một thực thể; các họ ``*-overview`` / ``*-contact`` / ``*-handling`` gộp
        # chúng lại thành một câu trả lời dùng được.
        # Node "Trường Đại học Nha Trang" mang cả lớp AcademicActor nên bộ sinh
        # đẻ ra bản sao "academic-rule-office-*" của cùng năm mẩu liên hệ.
        "academic-rule-office-address",
        "academic-rule-office-location",
        "academic-rule-office-phone",
        "academic-rule-office-email",
        "academic-rule-office-website",
        "organizational-unit-office-address",
        "organizational-unit-office-location",
        "organizational-unit-office-phone",
        "organizational-unit-office-email",
        "organizational-unit-office-website",
        "academic-procedure-label",
        "academic-procedure-summary-text",
        "academic-procedure-submitted-to-label",
        "academic-procedure-decided-by-label",
        "academic-procedure-reviewed-by-label",
        # Hỏi "nộp học phí ở đâu" phải ra CỔNG THANH TOÁN, không phải im lặng vì
        # thủ tục đó không nộp giấy cho ai.
        "academic-procedure-supports-payment-method-label",
        "academic-rule-label",
        "academic-rule-definition-text",
        "decision-document-number",
        "decision-issue-date",
        "decision-effective-from-semester",
        # Bốn họ thủ tục dưới đây dùng chung phần lớn thực thể neo và cùng trả lời
        # một câu hỏi của con người - "tôi muốn làm thủ tục X".
        # ``academic-procedure-overview`` trả cả tóm tắt lẫn các bước;
        # ``academic-procedure-handling`` trả cả biểu mẫu cần nộp.
        "academic-procedure-has-step-step-text",
        "academic-procedure-requires-form-label",
        # Cùng 2 neo, cùng hình dạng trả lời, nghĩa NGƯỢC nhau - sinh viên hỏi sàn
        # mà nhận trần là bị hướng dẫn sai hẳn. ``credit-load-rule-limits`` trả cả
        # hai, kèm nguyên văn dòng quy tắc: đó là chỗ DUY NHẤT nêu trần 32 tín chỉ
        # của chương trình 4,5 năm, mà ``maximumCredits`` = 27 thì trả lời sai cho
        # nhóm sinh viên đó.
        "credit-load-rule-maximum-credits",
        "credit-load-rule-minimum-credits",
        # Học bổng: bộ sinh đẻ ra bốn họ trả MẨU RỜI của cùng một mức học bổng -
        # riêng số tiền, riêng "VND", riêng "đồng trên học kỳ", riêng bậc đào tạo.
        # Không ai hỏi "học bổng loại giỏi dùng đơn vị tiền tệ gì".
        # ``scholarship-rate-details`` trả tên + số tiền + đơn vị + xếp loại.
        "scholarship-rate-amount",
        "scholarship-rate-applies-to-education-level-label",
        "scholarship-rate-billing-unit-label",
        "scholarship-rate-currency-code",
    }
)


def _tier(anchor_class: str, path: tuple[str, ...], *, opaque: bool) -> str:
    """Họ này có cần dữ liệu huấn luyện không?

    ``secondary`` vẫn truy vấn được ở runtime và vẫn phủ danh mục khả năng trả
    lời - nó chỉ không tiêu ngân sách dạy học. Các tiêu chí dưới đây đều nhận ra
    cùng một thứ: câu hỏi mà không người dùng nào đặt.
    """

    terminal = path[-1]
    document_part = anchor_class in _DOCUMENT_PART_CLASSES

    if document_part and terminal in _LOCATOR_TERMINALS:
        return "secondary"
    # Ràng buộc `document_part` là bắt buộc: `partOf` chỉ vô nghĩa khi dùng để đi
    # ngược cây cấu trúc VĂN BẢN. Một lớp nghiệp vụ về sau có quan hệ cùng tên thì
    # không được vạ lây - hiện chưa có lớp nào như vậy, nên đây là chặn trước.
    if (
        document_part
        and len(path) == 2
        and path[0] in _STRUCTURAL_RELATIONS
        and terminal == "rdfs:label"
    ):
        return "secondary"
    if document_part and path == ("rdfs:label",):
        return "secondary"
    if terminal in _INTERNAL_FLAG_TERMINALS:
        return "secondary"
    # MỌI họ neo trên bản ghi kỹ thuật. Người dùng không gọi tên chúng - họ hỏi
    # bằng một giá trị ("7,5 điểm xếp loại gì", "học phí ngành X khoá 65"), và các
    # câu đó đã có họ viết tay riêng. Hỏi theo lớp chỉ ra những câu về CẤU TRÚC
    # một bảng nội bộ ("bảng học phí gồm những khối ngành nào") mà không ai đặt.
    #
    # Vì bản ghi kỹ thuật luôn bị ràng buộc theo lớp (không có slot IRI), luật này
    # bao trùm cả trích dẫn, đường dẫn lẫn cột ngưỡng của chúng.
    if opaque:
        return "secondary"
    # Một dữ kiện nhỏ trỏ ngược về nguyên văn CẢ điều luật chứng minh nó. Hỏi
    # "đơn vị tính học phí là gì" - đáng lẽ nhận "đồng trên tín chỉ" - lại nhận
    # 2.892 ký tự nguyên văn Quyết định 729.
    if path == ("basedOn", "officialText"):
        return "secondary"
    # Trích dẫn và đường dẫn đứng một mình trên phần văn bản. Không ai hỏi riêng
    # chuỗi trích dẫn; người ta muốn NỘI DUNG KÈM NGUỒN, và các họ ``*-with-source``
    # đã làm đúng việc đó. Đường dẫn còn vô nghĩa hơn: mọi phần của cùng một tài
    # liệu dùng chung một URL, nên hỏi theo từng khoản là hàng trăm target trỏ về
    # vài đường dẫn giống nhau.
    if len(path) == 1 and terminal in {"citationLabel", "documentUrl"}:
        return "secondary"
    return "primary"


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


#: Đường đi ``officialText`` trả NGUYÊN VĂN một văn bản. Ba họ viết tay hỏi theo
#: số hiệu điều/khoản/điểm (``article-with-source`` …) đã trả nguyên văn KÈM căn
#: cứ và đường dẫn bản gốc; họ sinh tự động cho văn bản có TÊN thì chỉ trả mỗi
#: nguyên văn. Hai hình dạng lệch nhau cho cùng một kiểu câu hỏi - "Điều 22 nói
#: gì" có nguồn, "Phụ lục I nói gì" thì không - và chỗ lệch đó dụ model chọn nhầm.
#: Cho cả hai cùng hình dạng thì hết chỗ dụ.
VERBATIM_PATH = ("officialText",)
VERBATIM_COMPANIONS = ("citationLabel", "documentUrl")


def _verbatim_with_source_template() -> str:
    return (
        "SELECT ?nộidung ?căncứ ?xemtại WHERE { BIND(${anchor} AS ?d) "
        "?d :officialText ?nộidung ; :citationLabel ?căncứ ; :documentUrl ?xemtại . }"
    )


def _has_all(graph, anchors, predicates) -> bool:
    """Mọi neo trong nhóm có ĐỦ các thuộc tính đi kèm hay không.

    Thiếu dù một neo cũng phải trả về False: ba triple bắt buộc tạo một phép
    join, neo nào thiếu sẽ trả về RỖNG - tức là câu hỏi hợp lệ mà chatbot im
    lặng, kiểu hỏng tệ hơn hẳn việc trả lời thiếu cột.
    """

    return all(
        (URIRef(ONTOLOGY_NS + anchor), URIRef(ONTOLOGY_NS + predicate), None) in graph
        for anchor in anchors
        for predicate in predicates
    )


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
    used: set[str] = {CITATION_QUERY_ID}
    citation_anchors: set[str] = set()
    citation_classes: set[str] = set()
    for (classes, path), anchors in sorted(groups.items()):
        anchor_class = _primary_class(classes)
        opaque = is_opaque_record(graph, URIRef(ONTOLOGY_NS + anchors[0]))
        # Bản ghi kỹ thuật không được mang slot IRI - người dùng không gọi tên
        # chúng - nên chúng ở ngoài phép gộp và giữ họ ràng buộc theo lớp.
        if path in CITATION_PATHS and not opaque:
            # Thủ tục ĐỨNG NGOÀI họ căn cứ chung. ``source-citation`` phủ 223 neo,
            # trong đó có TRỌN neo của ``procedure-steps-with-source`` (22/22) và
            # ``procedure-requirements-with-source`` (17/17). Hệ quả: câu "cho xin
            # nguồn của thủ tục X" có ba đích đều hợp lệ và model buộc phải lụi.
            # Hai họ kia trả căn cứ KÈM nội dung nên hữu ích hơn; đường đi vẫn được
            # chúng phủ nên bỏ thủ tục ở đây không tạo lỗ hổng.
            if "AcademicProcedure" in classes:
                continue
            citation_anchors.update(anchors)
            citation_classes.update(classes)
            continue
        query_id = "-".join([_kebab(anchor_class), *(_kebab(p) for p in path)])
        suffix = 2
        while query_id in used:
            query_id = f"{query_id}-{suffix}"
            suffix += 1
        used.add(query_id)

        # Văn bản có TÊN thì trả nguyên văn KÈM căn cứ và đường dẫn, cùng hình
        # dạng với ``article-with-source`` / ``clause-with-source`` /
        # ``point-with-source``. Điều kiện đủ thuộc tính được kiểm trên ĐỒ THỊ chứ
        # không chốt cứng tên họ, nên thêm văn bản mới vào ontology là tự có nguồn.
        verbatim_with_source = (
            path == VERBATIM_PATH
            and not opaque
            and _has_all(graph, anchors, VERBATIM_COMPANIONS)
        )
        if verbatim_with_source:
            template = _verbatim_with_source_template()
            covered_paths = [list(VERBATIM_PATH)] + [[p] for p in VERBATIM_COMPANIONS]
        else:
            template = _template(path, anchored=not opaque, anchor_class=anchor_class)
            covered_paths = [list(path)]
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
                    {"anchor_classes": [anchor_class], "paths": covered_paths}
                ],
                "tier": _tier(anchor_class, path, opaque=opaque),
            }
        )
    if citation_anchors:
        families.append(_citation_family(citation_anchors, citation_classes))
    return _consolidate(families)


def _consolidate(families: list[dict[str, object]]) -> list[dict[str, object]]:
    """Gộp các họ KHÔNG phân biệt được với nhau ở bất kỳ khía cạnh nào đã khai.

    Bộ sinh nhóm theo lớp neo, nhưng template lại không nhắc tới lớp: ``${anchor}
    rdfs:label ?answer`` giống hệt nhau cho thủ tục, chứng chỉ, ngân hàng... Kết
    quả là 48 họ ``*-label`` cùng một câu SPARQL, chỉ khác danh sách neo.

    Gộp chúng lại là **phép biến đổi tương đương**: cùng template, hợp các danh
    sách neo rời nhau thì sinh ra đúng tập target cũ. Nhưng nó bỏ được một khối
    lớn họ na ná nhau - đúng thứ làm model lẫn khi chọn họ, và cũng là khối lượng
    soạn khung câu hỏi bị nhân lên vô ích.

    Khoá gộp gồm cả ``tier`` và ``domain``: hai họ khác tầng hoặc khác miền thì
    vẫn phân biệt được, không được nhập một.
    """

    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for family in families:
        key = (
            str(family["target_template"]),
            str(family["tier"]),
            str(family["domain"]),
        )
        grouped.setdefault(key, []).append(family)

    merged: list[dict[str, object]] = []
    for (template, tier, domain), group in grouped.items():
        anchors: set[str] = set()
        classes: set[str] = set()
        paths: set[tuple[str, ...]] = set()
        for family in group:
            slot = family["slots"].get("anchor")  # type: ignore[union-attr]
            if slot is not None:
                anchors.update(slot["values"])
            for selector in family["coverage"]:  # type: ignore[union-attr]
                classes.update(selector["anchor_classes"])
                paths.update(tuple(path) for path in selector["paths"])
        first = group[0]
        merged.append(
            {
                "query_id": _merged_query_id(domain, _naming_path(paths), tier)
                if len(group) > 1
                else first["query_id"],
                "domain": domain,
                "target_template": template,
                "slots": (
                    {"anchor": {"kind": "iri", "values": sorted(anchors)}}
                    if anchors
                    else {}
                ),
                "coverage": [
                    {
                        "anchor_classes": sorted(classes),
                        "paths": [list(path) for path in sorted(paths)],
                    }
                ],
                "tier": tier,
            }
        )
    return merged


def _naming_path(paths: set[tuple[str, ...]]) -> tuple[str, ...]:
    """Đường đi dùng để ĐẶT TÊN cho họ đã gộp.

    Mặc định lấy đường đi đầu theo thứ tự chữ cái - đủ dùng khi các đường đi
    ngang hàng nhau. Nhưng họ trả nguyên văn KÈM nguồn thì không ngang hàng:
    ``officialText`` mới là thứ người ta hỏi, ``citationLabel`` và ``documentUrl``
    chỉ đi kèm. Xếp chữ cái sẽ đặt tên nó là ``document-citation-label`` - đọc
    lên tưởng họ chỉ trả căn cứ, trong khi nó trả cả nguyên văn.
    """

    return VERBATIM_PATH if VERBATIM_PATH in paths else sorted(paths)[0]


def _merged_query_id(domain: str, path: tuple[str, ...], tier: str) -> str:
    """Tên cho họ đã gộp: giữ tên của một lớp neo cụ thể sẽ gây hiểu nhầm."""

    name = "-".join([domain, *(_kebab(part) for part in path)])
    return name if tier == "primary" else f"{name}-secondary"


def _citation_family(
    anchors: set[str],
    classes: set[str],
) -> dict[str, object]:
    """Một họ duy nhất trả căn cứ kèm đường dẫn bản gốc cho mọi neo gọi tên được.

    Hai triple bắt buộc tạo một phép join: neo thiếu ``documentUrl`` sẽ trả rỗng.
    ``catalogue_validation`` chỉ đối chiếu từng đường đi rời nên không tự bắt được
    lỗi đồng xuất hiện đó - ``tests/research/test_catalogue_validation.py`` canh nó.
    """

    return {
        "query_id": CITATION_QUERY_ID,
        "domain": "document",
        "target_template": (
            "SELECT ?căncứ ?xemtại WHERE { ${anchor} :basedOn ?part . "
            "?part :citationLabel ?căncứ ; :documentUrl ?xemtại . }"
        ),
        "slots": {"anchor": {"kind": "iri", "values": [f":{a}" for a in sorted(anchors)]}},
        "coverage": [
            {
                "anchor_classes": sorted(classes),
                "paths": [list(path) for path in CITATION_PATHS],
            }
        ],
        "tier": "primary",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=QUERY_CATALOGUE_PATH)
    return parser.parse_args()


def _manual_families(path: Path) -> list[dict[str, object]]:
    """Họ truy vấn viết tay, giữ nguyên thứ tự khai báo.

    Bộ sinh cơ học chỉ dựng được truy vấn đi theo một đường dẫn. Những câu hỏi
    hữu ích nhất lại cần so sánh ngưỡng ("7,5 điểm xếp loại gì", "70 tín chỉ là
    năm mấy", "học phí ngành X khoá 65") hoặc gom nhiều cột về một bản ghi. Mất
    tệp này là mất luôn các câu hỏi đó, nên nó là dữ liệu canonical.
    """

    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    args = _parse_args()
    generated = build()
    manual = _manual_families(QUERY_CATALOGUE_MANUAL_PATH)
    declared = {family["query_id"] for family in manual}
    families = manual + [f for f in generated if f["query_id"] not in declared]
    families.append(
        {
            "query_id": "no-information",
            "domain": "out-of-domain",
            "target_template": "không có thông tin",
            "slots": {},
            "coverage": [],
        }
    )
    # Họ viết tay và họ từ chối không khai tier; chúng luôn là primary.
    for family in families:
        family.setdefault("tier", "primary")
    # ... trừ những họ mà CÂU HỎI của chúng trùng với một họ khác.
    for family in families:
        if family["query_id"] in _QUESTION_DUPLICATES:
            family["tier"] = "secondary"

    Path(args.output).write_text(
        "".join(
            json.dumps(family, ensure_ascii=False, separators=(",", ":")) + "\n"
            for family in families
        ),
        encoding="utf-8",
    )
    anchored = sum(1 for family in families if family["slots"])
    primary = sum(1 for family in families if family["tier"] == "primary")
    print(
        f"{len(families)} họ truy vấn "
        f"({primary} primary, {len(families) - primary} secondary; "
        f"{len(manual)} viết tay, {anchored} có slot, "
        f"{len(families) - anchored} ràng buộc theo lớp) "
        f"-> {args.output}"
    )


if __name__ == "__main__":
    main()
