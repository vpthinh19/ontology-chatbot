"""Dựng danh mục truy vấn từ danh mục khả năng trả lời.

Bản trước sinh MỘT HỌ CHO MỖI CẶP (lớp neo, đường đi), ra 183 họ. Đo lại thì
86,3% số họ không trả cột nguồn và 87,4% trả đúng một cột trần trụi - tức là
danh mục tự nó dạy model làm hai việc mà đặc tả cấm. Sửa từng họ là vô vọng vì
chúng do máy sinh; phải sửa ở đây.

Bản này chỉ có MỘT hình dạng truy vấn, dùng cho mọi họ:

    lấy mọi giá trị chữ của neo và của các node kề nó, kèm tên cột lấy từ nhãn
    thuộc tính, kèm trích dẫn và đường dẫn bản gốc

Hình dạng đó trả 4 cột và luôn có chỗ cho nguồn, nên hai lỗi trên không thể tái
diễn từ khâu sinh. Nó cũng phủ đúng những gì danh mục khả năng trả lời liệt kê:
mọi đường đi ở đó dài 1 hoặc 2 chặng, đúng hai nhánh của khuôn.

Khác biệt duy nhất giữa các họ là **cách ghim neo**:

* **ghim bằng tên** - thủ tục, biểu mẫu, ngành, phần văn bản. Người hỏi gọi tên
  chúng, nên slot liệt kê IRI hữu hạn.
* **ghim gián tiếp** - bảng xếp loại, quy tắc quy đổi chứng chỉ, phí thanh
  toán. Không ai gọi tên "bậc xếp loại học lực khá"; người ta đưa ra một con số,
  hoặc một phương thức nộp tiền, rồi hỏi nó rơi vào đâu. Neo được tìm bằng phép
  so ngưỡng hoặc bằng quan hệ, chứ không bằng tên.

Nói cách khác: họ tham số KHÔNG phải một loại họ khác, nó là cùng một khuôn với
mệnh đề tìm neo khác. Đó là lý do tệp này ngắn hơn hẳn bản trước.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from ..catalogue import CatalogueError, load_catalogue
from ..runtime.sparql import load_ontology
from ..settings import (
    ANSWER_INVENTORY_PATH,
    ONTOLOGY_NS,
    QUERY_CATALOGUE_MANUAL_PATH,
    QUERY_CATALOGUE_PATH,
)

#: Các lớp trả lời cùng một kiểu câu hỏi thì gộp làm một họ. Tách ra chỉ tạo ra
#: những họ gần giống hệt nhau, và đó chính là chế độ lỗi đã đo được ở v2: model
#: nhận đúng thực thể nhưng chọn nhầm họ.
CLASS_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "document-part",
        "document",
        (
            "Chapter",
            "Article",
            "Clause",
            "Point",
            "Appendix",
            "DocumentSection",
        ),
    ),
    ("official-document", "document", ("Decision", "Regulation", "GuidanceDocument", "FormCatalogue")),
    ("certificate", "certificate", ("Certificate", "LanguageCertificate", "ComputerCertificate")),
)

#: Lớp neo -> miền, dùng cho báo cáo độ phủ.
DOMAIN_OF_CLASS = {
    "AcademicProcedure": "procedure",
    "AcademicCase": "procedure",
    "CaseResolution": "procedure",
    "ProcedureStep": "procedure",
    "Requirement": "procedure",
    "Deadline": "procedure",
    "Outcome": "procedure",
    "Consequence": "procedure",
    "OrganizationalUnit": "procedure",
    "AcademicActor": "procedure",
    "PaymentMethod": "tuition",
    "PaymentFeeRule": "tuition",
    "Bank": "tuition",
    "BillingUnit": "tuition",
    "ScholarshipRate": "tuition",
    "FormDocument": "form",
    "FormCatalogueEntry": "form",
}
DEFAULT_DOMAIN = "academic-rule"

#: Neo KHÔNG gọi tên được. Mỗi mục: mệnh đề tìm neo, các slot, và miền.
#:
#: Đây là chỗ duy nhất trong tệp phải viết tay, vì mỗi bảng ngưỡng dùng một cặp
#: trường khác nhau và không suy ra cơ học được. Danh sách ngắn có chủ đích: chỉ
#: những lớp mà người hỏi không gọi tên được mới nằm đây. Lớp chỉ mang số hiệu -
#: điều, khoản, biểu mẫu - không thuộc nhóm này; số hiệu là định danh, khớp bằng
#: phép bằng, và chúng được ghim bằng tên như mọi neo gọi tên được khác.
INDIRECT_ANCHORS: tuple[dict[str, object], ...] = (
    {
        # Không ai gọi tên "phí VNPAY đối với ngân hàng khác". Người ta hỏi
        # "đóng qua VNPay có mất phí không", tức là ghim bằng PHƯƠNG THỨC NỘP.
        # Đây là ca cho thấy "ghim gián tiếp" không đồng nghĩa với "ghim bằng số".
        "query_id": "payment-fee-by-method",
        "domain": "tuition",
        "classes": ("PaymentFeeRule",),
        "slots": {"phuongthuc": "iri"},
        "iri_class": "PaymentMethod",
        "where": "?x a :PaymentFeeRule ; :appliesToPaymentMethod ${phuongthuc} .",
    },
)

#: Tám bảng còn lại, mỗi bảng ứng với một ý định độc lập. Ba bảng cuối giới
#: thiệu thực thể; các thực thể vẫn tồn tại, còn bảng giữ nguyên bố cục nguồn.
SOURCE_TABLE_FAMILIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("academic-performance-table", "academic-rule", ("Regulation1052Article18Clause02Table01",)),
    ("study-year-classification-table", "academic-rule", ("Regulation1052Article19Clause01Table01",)),
    ("graduation-classification-table", "academic-rule", ("Regulation1052Article23Clause02Table01",)),
    ("class-size-table", "academic-rule", ("Regulation1052Appendix1Table01",)),
    ("language-course-classification-table", "academic-rule", ("Decision1965Article01Table01",)),
    ("language-course-assessment-table", "academic-rule", ("Decision1965Article01Table02",)),
    ("certificate-catalogue-table", "certificate", ("Regulation1052Appendix2Table06",)),
    ("academic-program-catalogue-table", "academic-rule", ("Decision729AppendixIITable01",)),
    # Hai bảng mức học bổng, nạp 15/8/2026. Tách làm hai họ chứ không gộp một, vì
    # cùng một xếp loại cho ra hai số tiền khác nhau tuỳ chương trình chuẩn hay
    # đặc biệt - gộp lại thì câu trả lời mơ hồ đúng ở chỗ người hỏi cần rõ nhất.
    ("scholarship-rate-table-standard-program", "tuition", ("Decision317Article01Table01",)),
    ("scholarship-rate-table-special-program", "tuition", ("Decision317Article02Table01",)),
)

#: Bốn ý định người dùng, sáu bảng nguồn. Không còn slot chứng chỉ hay điều kiện
#: trên từng dòng: chọn đúng họ là chọn thẳng node bảng, rồi trả nguyên khối để
#: LLM lớn tự đọc. Hai nhóm có hai bảng vì công văn tách tiếng Anh và các ngoại
#: ngữ khác thành hai bảng độc lập.
CONVERSION_TABLE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "certificate-conversion-table-english-language-major-student",
        ("Regulation1052Appendix2Table05",),
    ),
    (
        "certificate-conversion-table-special-program-non-language-major-student",
        ("Regulation1052Appendix2Table03", "Regulation1052Appendix2Table04"),
    ),
    (
        "certificate-conversion-table-standard-program-non-language-major-student",
        ("Regulation1052Appendix2Table01", "Regulation1052Appendix2Table02"),
    ),
    (
        "certificate-conversion-table-moi-doi-tuong",
        ("Regulation1052Appendix3Table01",),
    ),
)

#: Khuôn chung. ``${bind}`` là mệnh đề ghim neo, phần còn lại giống nhau ở mọi họ.
#:
#: Bốn cột, và hai trong số đó là nguồn - nên không họ nào sinh ra từ đây có thể
#: vi phạm luật "phải kèm nguồn" hay "không được trả một cột".
#:
#: ĐÃ THỬ chặn nhánh hai đi sang LỚP bằng ``FILTER(?l != rdf:type)``, và BỎ. Nó
#: dọn được 46 dòng kiểu ``tên gọi = Khoản`` vốn không trích dẫn được vì lớp không
#: đến từ văn bản nào - nhưng nó cũng làm họ ``academic-actor-facts`` mất sạch nội
#: dung: node vai trò chỉ có đúng tên gọi, bỏ nhãn lớp đi thì dump còn một dòng và
#: bộ sinh từ chối. Dòng nhãn lớp không đánh lừa ai, chỉ để trống cột nguồn, nên
#: giữ lại là đổi ít lấy nhiều.
#:
#: ``FILTER(?p != skos:altLabel)`` giấu nhãn phụ khỏi câu trả lời. Nhãn phụ là
#: phương tiện để TÌM RA thực thể, không phải nội dung trả lời; thả vào thì một
#: thủ tục phình thêm chục dòng "bảo lưu", "phòng CTSV".
#: Nguồn được GỘP chứ không nối thẳng. Nối thẳng thì mỗi nguồn NHÂN ĐÔI toàn bộ
#: dữ kiện: quy tắc phí VNPAY có ba nguồn nên 17 dữ kiện thành 51 dòng, hai quy
#: tắc thành 102 - vượt trần 100 dòng của runtime và truy vấn ném lỗi, sinh viên
#: không nhận được gì. Gộp lại còn 34 dòng và vẫn thấy đủ ba nguồn.
#:
#: Đây là lỗi của KHUÔN chứ không của riêng họ nào: mọi node có nhiều hơn một
#: :basedOn đều bị nhân lên như vậy.
#: KHÔNG dùng DISTINCT. Hai cột phải khớp nhau theo thứ tự: trích dẫn thứ i đi
#: với đường dẫn thứ i. ``DISTINCT`` trên đường dẫn gộp mất bản trùng - quy tắc
#: phí VNPAY có ba nguồn nhưng hai trong số đó cùng một thông báo, nên ra 3 trích
#: dẫn với 2 đường dẫn và người đọc không biết ghép cái nào với cái nào. Đường
#: dẫn lặp lại là đúng: hai mục khác nhau của cùng một văn bản.
#:
#: Nhánh UNION thứ hai cho PHẦN VĂN BẢN tự dẫn chính nó. Điều 24 không có
#: ``basedOn`` - nó LÀ nguồn - nên nếu chỉ đi theo ``basedOn`` thì cả tầng văn
#: bản, hơn 280 neo, trả lời với cột nguồn RỖNG. Luật "mọi họ phải có cột nguồn"
#: vẫn xanh vì nó chỉ kiểm tên cột có mặt, không kiểm cột có giá trị.
#: HAI CHI TIẾT KHÔNG ĐƯỢC BỎ, cả hai đều đã gây lỗi thật:
#:
#: 1. ``STR(?u)`` là BẮT BUỘC. ``documentUrl`` khai kiểu ``xsd:anyURI``, mà
#:    ``GROUP_CONCAT`` theo chuẩn chỉ nhận chuỗi. rdflib dễ tính nên vẫn nối,
#:    Oxigraph đúng chuẩn nên trả UNBOUND - và đó là điều đã xảy ra: đổi engine
#:    làm mất cột đường dẫn ở **471/521 đích** suốt nhiều tháng mà bộ kiểm im
#:    lặng, vì nó chỉ kiểm tên cột có mặt chứ không kiểm cột có giá trị.
#: 2. Trích dẫn và đường dẫn nay lấy RIÊNG bằng hai ``OPTIONAL``, chỉ cần MỘT
#:    trong hai là đủ để coi như có nguồn. Hợp đồng nguồn là "công văn HOẶC web
#:    chính chủ", nên một trang web không có Điều/Khoản để trích dẫn vẫn phải
#:    dẫn được nguồn. Bản trước đòi cả hai bằng dấu ``;`` nên thiếu một là mất
#:    sạch cả hai, âm thầm.
#:
#: ``COALESCE`` giữ chuỗi rỗng thay cho giá trị vắng để HAI CỘT KHỚP NHAU THEO
#: THỨ TỰ - ``GROUP_CONCAT`` bỏ qua giá trị unbound, nên thiếu nó thì trích dẫn
#: thứ i không còn đi với đường dẫn thứ i.
#: 3. Đường dẫn nhận CẢ ``documentUrl`` LẪN ``webPageUrl``. Hai tên cho cùng một
#:    thứ: phần công văn dùng cái đầu, còn tài liệu web (hướng dẫn nộp học phí,
#:    trang cơ cấu tổ chức, danh mục biểu mẫu) dùng cái sau. Chỉ nhận một tên là
#:    năm tài liệu web tự trả lời về mình mà KHÔNG có đường dẫn nào - tức nguồn
#:    web bị đối xử kém hơn công văn, trái với hợp đồng đã chốt.
_SOURCE_CLAUSE = "OPTIONAL{?x :sourceCitation ?nguon;:sourceLink ?duongdan} "

DUMP_TEMPLATE = (
    "SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE { "
    "${bind} "
    "{ ?x ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh "
    + _SOURCE_CLAUSE + "} "
    "UNION "
    "{ ?x ?l ?con . ?con ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh "
"OPTIONAL{?con :sourceCitation ?nguon;:sourceLink ?duongdan} } "
    "FILTER(?p!=skos:altLabel&&?p!=:sourceCitation&&?p!=:sourceLink) "
    "}"
)

# Với neo IRI hữu hạn, không ghim ``?x`` bằng ``BIND``: Oxigraph mất hàng nghìn
# lần thời gian cho hình dạng đó. IRI được đặt thẳng vào hai nhánh lấy dữ kiện.
#
# Phần nguồn dùng đường ``:basedOn?``: độ dài 0 lấy chính neo văn bản, độ dài 1
# lấy căn cứ của node nghiệp vụ. Cách này giữ đúng hai trường hợp của hai nhánh
# ``UNION`` cũ mà chỉ phải ghi IRI neo thêm một lần. Đây không chỉ là rút gọn
# hình thức: tên IRI dài từng làm 448/523 target vượt trần 320 token của ViT5.
# Subquery chỉ phục vụ một neo cố định nên không cần chiếu/group theo ``?x``.
# ``HAVING`` giữ hai cột nguồn ở trạng thái unbound khi neo không có nguồn,
# thay vì biến chúng thành chuỗi rỗng do aggregate trên tập nghiệm rỗng.
# Nguồn gắn theo NODE SỞ HỮU dữ kiện, không theo neo. Bản trước đặt một
# ``OPTIONAL`` duy nhất ở ngoài, chiếu nguồn của neo cho MỌI dòng - kể cả dòng
# mượn qua nhánh thứ hai. Hậu quả đo được 15/8/2026: 304 dòng dataset trả dữ kiện
# của một văn bản kèm trích dẫn của văn bản khác. Nặng nhất là hỏi "thủ tục xin
# miễn học miễn thi" thì ra ``hộp thư = daotao@ntu.edu.vn`` kèm nguồn "khoản 5
# Điều 21 Quy chế đào tạo" - khoản đó nói về các trường hợp được miễn thi, không
# có địa chỉ email nào. Email đến từ trang Cơ cấu tổ chức, một tài liệu khác hẳn.
#
# Sinh viên bấm vào nguồn mà không thấy điều vừa được trả lời thì trích dẫn còn
# tệ hơn không có: nó tạo lòng tin sai.
#
# KHÔNG có mệnh đề lui trong truy vấn. Bản đầu thêm hai ``OPTIONAL`` cộng hai
# ``BIND`` để lui về nguồn của neo khi node cho mượn thiếu trích dẫn, và trả giá
# đắt: đích dài thêm khoảng 60 token, đẩy 551/567 đích vượt trần sinh 320 token
# của ViT5 - tức model seq2seq không sinh nổi chính đích của nó.
#
# Chỗ thiếu nằm ở DỮ LIỆU chứ không ở truy vấn: 17 node văn bản không khai
# ``citationLabel`` cho chính mình, nên khi một điều khoản mượn số hiệu và ngày
# ban hành của văn bản mẹ thì dòng đó không có nguồn. Đã khai đủ 17 trích dẫn ấy.
# Sửa dữ liệu thì truy vấn ngắn lại, và văn bản cũng tự mô tả được mình.
# Bản sửa đầu bỏ bước lui này và làm dữ kiện thiếu nguồn vọt từ 4,1% lên 17,2%:
# phần lớn là dữ kiện ĐỊNH DANH của văn bản mẹ - số hiệu, ngày ban hành, tên gọi
# - lấy qua ``:inDocument``. Node văn bản không khai ``citationLabel`` cho chính
# nó, mà trích dẫn của điều khoản đang hỏi thì vốn đã nêu đúng văn bản ấy. Lui về
# neo ở đó là ĐÚNG, không phải nhân nhượng.
NAMED_DUMP_TEMPLATE = (
    "SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE { "
    "{ ${anchor} ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh "
    "OPTIONAL{${anchor} :sourceCitation ?nguon;:sourceLink ?duongdan} } "
    "UNION "
    "{ ${anchor} ?l ?con . ?con ?p ?giatri . FILTER(isLiteral(?giatri)) ?p rdfs:label ?thuoctinh "
"OPTIONAL{?con :sourceCitation ?nguon;:sourceLink ?duongdan} } "
    "FILTER(?p!=skos:altLabel&&?p!=:sourceCitation&&?p!=:sourceLink) "
    "}"
)

# Bảng là ngoại lệ có chủ đích đối với khuôn duyệt node kề ở trên.
# Mỗi họ phải trả đúng nguyên khối của các node đã ghim: đi qua ``partOf`` sẽ
# kéo cả Phụ lục mẹ vào, vừa nhân dòng vừa gắn nhầm trích dẫn bảng con cho văn
# bản của cha.
TABLE_DUMP_TEMPLATE = (
    "SELECT ?thuoctinh ?giatri ?nguon ?duongdan WHERE { "
    "${bind} "
    "?x :citationLabel ?nguon ; :documentUrl ?duongdan . "
    "{ "
    # Không thụt lề các dòng nối tiếp: khuôn này được ghép thành MỘT dòng,
    # nên khoảng trắng thụt lề sẽ thành khoảng trắng đôi trong truy vấn, và
    # phép kiểm "target phải là một dòng canonical" sẽ đỏ.
    "{ VALUES ?p { :verbatimTableText :citationLabel :documentUrl } "
    "?x ?p ?giatri . ?p rdfs:label ?thuoctinh } "
    "UNION "
    "{ ?x rdfs:label ?giatri . BIND(\"nhãn tiếng Việt\"@vi AS ?thuoctinh) } "
    "UNION "
    "{ VALUES ?p { :inDocument :partOf } "
    "?x ?p ?related . ?related rdfs:label ?giatri . ?p rdfs:label ?thuoctinh } "
    "} "
    "}"
)


_COLUMN = re.compile(r"^[a-z][a-zA-Z0-9]*$")
_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


class CatalogueBuildError(ValueError):
    """Bộ dựng từ chối sinh ra một họ vi phạm luật của danh mục."""


def _kebab(name: str) -> str:
    return _CAMEL.sub("-", name).lower()


def _local(node: URIRef) -> str:
    return str(node).rsplit("#", 1)[-1]


def _classes_of(graph: Graph, node: URIRef) -> list[str]:
    """Lớp của một node, bỏ owl:NamedIndividual và lớp ngoài tên miền dự án."""

    return sorted(
        _local(t)
        for t in graph.objects(node, RDF.type)
        if t != OWL.NamedIndividual and str(t).startswith(ONTOLOGY_NS)
    )


def _most_specific(graph: Graph, names: list[str]) -> str:
    """Lớp con cùng trong danh sách - lớp không phải cha của lớp nào khác ở đó."""

    if not names:
        return ""
    parents = {
        name: {_local(p) for p in graph.objects(URIRef(ONTOLOGY_NS + name), RDFS.subClassOf)}
        for name in names
    }
    leaves = [n for n in names if not any(n in parents[m] for m in names)]
    return sorted(leaves)[0] if leaves else sorted(names)[0]


#: Trần dòng của runtime. Truy vấn vượt là ném lỗi, người hỏi không nhận được gì.
ROW_LIMIT = 100
#: Số tổ hợp slot thử mỗi họ. Lấy mẫu trải đều là đủ, vì họ phình thường phình
#: ở nhiều tổ hợp chứ không riêng một.
_SAMPLED_COMBINATIONS = 40
_SAMPLE_NUMBERS = ("0", "5", "6.5", "35", "68", "70", "105", "600")


def _check_row_limit(graph: Graph, family: dict[str, object]) -> None:
    """Không họ nào được trả quá trần dòng của runtime.

    Ba luật ở ``_check`` chỉ soi HÌNH DẠNG họ - đủ cột, có cột nguồn, tên cột
    ASCII. Chúng không thấy được họ trả về quá nhiều dòng, và đó là cách một họ
    vỡ ở runtime mà mọi phép kiểm vẫn xanh: họ phí thanh toán từng trả 102 dòng
    cho cổng VNPAY, tức là ném lỗi thay vì trả lời.
    """

    import random
    from itertools import product

    from ..runtime.sparql import SparqlError, execute_select

    slots = dict(family["slots"])  # type: ignore[arg-type]
    pools = [
        tuple(slot["values"]) if slot["kind"] == "iri" else _SAMPLE_NUMBERS
        for slot in slots.values()
    ]
    # Lấy mẫu TRẢI ĐỀU, không phải 24 tổ hợp đầu. ``product`` chạy chậm nhất ở
    # slot đầu tiên, nên lấy phần đầu là chỉ thử đúng MỘT chứng chỉ trong mười
    # tám - đúng kiểu chốt chặn nhìn thì có mà không canh được gì. Hạt giống cố
    # định để bộ dựng vẫn tái lập được.
    space = list(product(*pools)) if pools else [()]
    if len(space) > _SAMPLED_COMBINATIONS:
        space = random.Random(0).sample(space, _SAMPLED_COMBINATIONS)
    combos = space
    for values in combos:
        query = str(family["target_template"])
        for name, value in zip(slots, values):
            query = query.replace("${" + name + "}", value)
        try:
            rows = execute_select(graph, query, max_rows=ROW_LIMIT * 10)
        except SparqlError:
            continue
        if len(rows) > ROW_LIMIT:
            raise CatalogueBuildError(
                f"{family['query_id']}: trả {len(rows)} dòng với {dict(zip(slots, values))}, "
                f"vượt trần {ROW_LIMIT} của runtime"
            )


def _check(family: dict[str, object]) -> dict[str, object]:
    """Ba luật của đặc tả, chặn tại khâu sinh chứ không sửa tay về sau."""

    query_id = family["query_id"]
    target = str(family["target_template"])
    head = target.split("WHERE", 1)[0]
    columns = re.findall(r"\?(\w+)", head)

    if len(columns) < 2:
        raise CatalogueBuildError(f"{query_id}: họ chỉ trả {len(columns)} cột")
    if not {"nguon", "duongdan"} & set(columns):
        raise CatalogueBuildError(f"{query_id}: họ không có cột nguồn")
    bad = [c for c in columns if not _COLUMN.match(c)]
    if bad:
        raise CatalogueBuildError(f"{query_id}: tên cột không hợp lệ: {bad}")
    return family


def _grouped_inventory(
    graph: Graph, entries: list[dict]
) -> dict[str, dict[str, set]]:
    """Gom mục supported theo nhóm lớp neo."""

    group_of: dict[str, str] = {}
    for group_id, _, classes in CLASS_GROUPS:
        for name in classes:
            group_of[name] = group_id

    buckets: dict[str, dict[str, set]] = defaultdict(
        lambda: {"paths": set(), "anchors": set(), "classes": set()}
    )
    for entry in entries:
        node = URIRef(ONTOLOGY_NS + str(entry["anchor"]))
        specific = _most_specific(graph, _classes_of(graph, node))
        if not specific:
            continue
        key = group_of.get(specific, specific)
        bucket = buckets[key]
        bucket["paths"].add(tuple(entry["path"]))
        bucket["anchors"].add(str(entry["anchor"]))
        bucket["classes"].add(specific)
    return buckets


def _domain_for(classes: set[str], group_id: str) -> str:
    for group, domain, _ in CLASS_GROUPS:
        if group == group_id:
            return domain
    for name in sorted(classes):
        if name in DOMAIN_OF_CLASS:
            return DOMAIN_OF_CLASS[name]
    return DEFAULT_DOMAIN


def _indirect_family(graph: Graph, spec: dict, bucket: dict[str, set]) -> dict[str, object]:
    where = str(spec["where"])
    slots: dict[str, object] = {}
    for name, kind in dict(spec["slots"]).items():  # type: ignore[arg-type]
        if kind == "number":
            slots[name] = {"kind": "number"}
            continue
        class_name = str(spec.get(f"iri_class_{name}", spec["iri_class"]))
        values = sorted(
            f":{_local(node)}"
            for node in graph.subjects(RDF.type, URIRef(ONTOLOGY_NS + class_name))
        )
        slots[name] = {"kind": "iri", "values": values}
    return _check(
        {
            "query_id": spec["query_id"],
            "domain": spec["domain"],
            "target_template": DUMP_TEMPLATE.replace("${bind}", where),
            "slots": slots,
            "coverage": [
                {
                    "anchor_classes": sorted(bucket["classes"]),
                    "paths": [list(path) for path in sorted(bucket["paths"])],
                }
            ],
        }
    )


def _table_families(
    graph: Graph,
    bucket: dict[str, set],
    declarations: tuple[tuple[str, str, tuple[str, ...]], ...],
    class_name: str,
) -> list[dict[str, object]]:
    """Ghim từng họ thẳng vào node bảng nguồn, không đi qua node con."""

    families = []
    for query_id, domain, table_names in declarations:
        anchors = [f":{name}" for name in table_names]
        where = "VALUES ?x { " + " ".join(anchors) + " }"
        paths = []
        for path in sorted(bucket["paths"]):
            nodes: set[object] = {
                URIRef(ONTOLOGY_NS + table_name) for table_name in table_names
            }
            for component in path:
                predicate = (
                    RDFS.label
                    if component == "rdfs:label"
                    else URIRef(ONTOLOGY_NS + component)
                )
                nodes = {
                    value
                    for node in nodes
                    if isinstance(node, URIRef)
                    for value in graph.objects(node, predicate)
                }
            if nodes:
                paths.append(list(path))
        families.append(
            _check(
                {
                    "query_id": query_id,
                    "domain": domain,
                    "target_template": TABLE_DUMP_TEMPLATE.replace("${bind}", where),
                    "slots": {},
                    "coverage": [
                        {
                            "anchor_classes": [class_name],
                            "anchors": list(table_names),
                            "paths": paths,
                        }
                    ],
                }
            )
        )
    return families


def _named_family(group_id: str, bucket: dict[str, set]) -> dict[str, object]:
    return _check(
        {
            "query_id": f"{_kebab(group_id)}-facts",
            "domain": _domain_for(set(bucket["classes"]), group_id),
            "target_template": NAMED_DUMP_TEMPLATE,
            "slots": {
                "anchor": {
                    "kind": "iri",
                    "values": [f":{name}" for name in sorted(bucket["anchors"])],
                }
            },
            "coverage": [
                {
                    "anchor_classes": sorted(bucket["classes"]),
                    "paths": [list(path) for path in sorted(bucket["paths"])],
                }
            ],
        }
    )


def build(
    graph: Graph | None = None,
    inventory_path: Path = ANSWER_INVENTORY_PATH,
) -> list[dict[str, object]]:
    graph = graph if graph is not None else load_ontology()
    inventory = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    entries = [e for e in inventory["entries"] if e.get("status") == "supported"]
    buckets = _grouped_inventory(graph, entries)

    families: list[dict[str, object]] = []
    handled: set[str] = set()
    if "CertificateConversionTable" in buckets:
        declarations = tuple(
            (query_id, "certificate", table_names)
            for query_id, table_names in CONVERSION_TABLE_FAMILIES
        )
        families.extend(
            _table_families(
                graph,
                buckets["CertificateConversionTable"],
                declarations,
                "CertificateConversionTable",
            )
        )
        handled.add("CertificateConversionTable")
    if "DocumentTable" in buckets:
        families.extend(
            _table_families(
                graph,
                buckets["DocumentTable"],
                SOURCE_TABLE_FAMILIES,
                "DocumentTable",
            )
        )
        handled.add("DocumentTable")
    for spec in INDIRECT_ANCHORS:
        for name in tuple(spec["classes"]):  # type: ignore[arg-type]
            if name not in buckets:
                continue
            families.append(_indirect_family(graph, spec, buckets[name]))
            handled.add(name)
            break
    for group_id in sorted(buckets):
        if group_id in handled:
            continue
        families.append(_named_family(group_id, buckets[group_id]))
    for family in families:
        _check_row_limit(graph, family)
    return families


def _manual_families(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=QUERY_CATALOGUE_PATH)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    graph = load_ontology()
    generated = build(graph)
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
    for family in families:
        family.setdefault("tier", "primary")

    args.output.write_text(
        "".join(json.dumps(f, ensure_ascii=False) + "\n" for f in families),
        encoding="utf-8",
    )
    try:
        load_catalogue(args.output)
    except CatalogueError as exc:
        raise SystemExit(f"danh mục vừa sinh không hợp lệ: {exc}") from exc
    print(f"{len(families)} họ -> {args.output}")


if __name__ == "__main__":
    main()
