"""Tầng văn bản phải chép đúng nguyên văn công văn.

Tầng nghiệp vụ được canh bởi ``test_drafting_rules``. Tầng văn bản thì trước nay
không có gì canh, dù nó là chứng cứ cho toàn bộ câu trả lời của chatbot: sai một
chữ ở đây là chatbot trích dẫn sai một cách rất thuyết phục.

Các kiểm tra này đối chiếu thẳng với ``references/`` — thư mục giữ bản sao công
văn gốc. Chúng là ràng buộc thường trực, không phải kiểm tra một lần khi dựng
ontology: bất cứ ai sửa ``ontology.ttl`` về sau đều có thể vô tình làm lệch.
"""

from __future__ import annotations

import re
import unicodedata

import pytest
from rdflib import RDF, OWL, Literal, URIRef

from ontchatbot.settings import ONTOLOGY_NS, PROJECT_ROOT

#: Công văn có bản sao dạng văn bản trong ``references/``.
#:
#: ``Qd317.md`` là bản OCR từ ảnh chụp công văn giấy, đã được đối chiếu lại với
#: chính bản scan: bộ OCR có thói quen **sửa lỗi của công văn** (tự thêm "trở
#: lên" vào chỗ bản gốc chỉ ghi "trở", tự bỏ chữ lặp "Trường Trường"). Đã hoàn
#: nguyên về đúng mặt chữ bản gốc - ontology trích dẫn công văn thật, không
#: trích dẫn bản đã được máy làm sạch.
#:
#: ``Qd753.md`` cũng là bản OCR, và Điều 10 của nó từng mất dấu ở bốn chỗ:
#: "học phan", "dé nghị", "quản ly", "Mdu số 2". Đã mở bản scan ra đối chiếu và
#: hoàn nguyên về đúng mặt chữ - đây là sửa lỗi CỦA MÁY, không phải sửa lỗi của
#: công văn. Bản scan nay nằm ở ``references/Qd753.pdf`` để lần sau khỏi phải đi
#: tìm.
#:
#: ``Qd1965.md`` thì bản OCR hỏng tới mức không cứu được - hai bảng vỡ nát, chữ
#: dính vào nhau. Đã chép tay lại toàn bộ từ bản scan. Lưu ý một chỗ dễ bị
#: "sửa hộ": Điều 2 của công văn ghi *"có hiệu lực kể ngày ký ban hành"*, thiếu
#: chữ "từ". Đó là lỗi CỦA CÔNG VĂN và phải giữ nguyên.
SOURCE_FILES = (
    "Qd1052.md",
    "Qd729.md",
    "huong_dan_dong_hoc_phi.md",
    "Qd317.md",
    "DongHocPhi_VCB_2021.md",
    "Qd753.md",
    "Qd1965.md",
)

#: Tài liệu lấy nội dung từ các tệp trên. Danh mục biểu mẫu không nằm đây vì
#: nguồn của nó là một trang web, chép về sẽ khác hình thức.
TEXT_SOURCED_DOCUMENTS = (
    "Decision1052",
    "Regulation1052",
    "Decision729",
    "TuitionPaymentGuidance",
    "Decision317",
    "VNPAYPaymentGuidance",
    "Regulation753",
    "Decision1965",
)

#: Cả 14 bảng được trả nguyên khối cho LLM. Dòng đầu xác định bảng trực tiếp,
#: tránh phải dựng lại bảng từ node con hoặc dựa vào heading có thể lặp.
VERBATIM_TABLE_SOURCES = {
    # Hai bảng mức học bổng nạp 15/8/2026. Trước đó sáu mức học bổng dẫn nguồn về
    # câu dẫn "... cụ thể như sau:" của Điều 1/Điều 2 - một câu KHÔNG chứa số tiền
    # nào. Khai ở đây để phép kiểm đối chiếu từng ký tự với ``references/Qd317.md``.
    "ScholarshipRateTableStandardProgram": (
        "Qd317.md",
        "| STT | Xếp loại học bổng | Học bổng 05 tháng / học kỳ (VNĐ) |",
    ),
    "ScholarshipRateTableSpecialProgram": (
        "Qd317.md",
        "| STT | Xếp loại học bổng | Học bổng 05 tháng - chương trình đào tạo đặc biệt / học kỳ (VNĐ) |",
    ),
    "AcademicPerformanceTable": (
        "Qd1052.md",
        "| **Điểm trung bình chung** | **Mức xếp loại** |",
    ),
    "StudyYearClassificationTable": (
        "Qd1052.md",
        "| **TT** | **Số tín chỉ đã tích lũy** | **Xếp trình độ năm học** |",
    ),
    "GraduationClassificationTable": (
        "Qd1052.md",
        "| **TT.** | **Điểm trung bình chung tích lũy của toàn khoá** | **Xếp loại** |",
    ),
    "ClassSizeTable": (
        "Qd1052.md",
        "| **TT** | **Học phần** | **Số lượng sinh viên** | |",
    ),
    "EnglishConversionTableStandardProgram": (
        "Qd1052.md",
        "| Khung NLNN 6 bậc | CEFR | TOEIC | TOEFL (iBT) | IELTS | Linguaskill | Aptis (General) | Cambridge English Scale | Quy đổi thành điểm 10 |",
    ),
    "OtherLanguageConversionTableStandardProgram": (
        "Qd1052.md",
        "| Khung NLNN 6 bậc | Tiếng Trung (HSK) | Tiếng Trung (TOCFL) | Tiếng Nhật (JLPT) | Tiếng Nhật (JPT) | Tiếng Nga (TPKN) | Tiếng Pháp (DELF) | Tiếng Pháp (TCF) | Tiếng Hàn (TOPIK) | Tiếng Hàn (KLPT) | Quy đổi thành điểm 10 |",
    ),
    "EnglishRequirementTableSpecialProgram": (
        "Qd1052.md",
        "| TT | Chương trình | KNLNN / CEFR | TOEIC | IELTS | TOEFL iBT | Linguaskill | Aptis (General) | Cambridge English Scale |",
    ),
    "OtherLanguageRequirementTableSpecialProgram": (
        "Qd1052.md",
        "| TT | Chương trình | Tiếng Trung (HSK) | Tiếng Trung (TOCFL) | Tiếng Nhật (JLPT) | Tiếng Nhật (JPT) | Tiếng Nga (TPKN) | Tiếng Pháp (DELF) | Tiếng Pháp (TCF) | Tiếng Hàn (TOPIK) |",
    ),
    "SecondLanguageConversionTableEnglishMajor": (
        "Qd1052.md",
        "| Khung NLNN 6 bậc | Tiếng Trung (HSK) | Tiếng Trung (TOCFL) | Tiếng Nhật (JLPT) | Tiếng Nhật (JPT) | Tiếng Nga (TPKN) | Tiếng Pháp (DELF) | Tiếng Pháp (TCF) | Tiếng Hàn (TOPIK) | Tiếng Hàn (KLPT) | Quy đổi thành điểm 10 cho các cấp độ HP |",
    ),
    "ForeignLanguageCertificateAbbreviationTable": (
        "Qd1052.md",
        "| TT | Ngoại ngữ | Từ viết tắt | Viết đầy đủ |",
    ),
    "ComputerCertificateConversionTable": (
        "Qd1052.md",
        "| TT | Điểm IC3 | Điểm ICDL | Điểm MOS | Điểm quy đổi / Điểm thưởng |",
    ),
    "ForeignLanguageCourseCatalogueTable": (
        "Qd1965.md",
        "| STT | Học phần | Tín chỉ | Khung NLNN tương ứng | Khóa 67 trở về trước | Khóa 68 trở đi |",
    ),
    "ForeignLanguageCourseAssessmentTable": (
        "Qd1965.md",
        "| STT | Học phần | Thành phần đánh giá | Tỷ trọng |",
    ),
    "AcademicProgramCatalogueTable": (
        "Qd729.md",
        "| **TT** | **Tên ngành đào tạo** |",
    ),
}


def _normalise(text: str) -> str:
    """Bỏ khác biệt hình thức, giữ nguyên chữ."""

    text = unicodedata.normalize("NFC", str(text))
    text = re.sub(r"<br\s*/?>", " ", text).replace("&nbsp;", " ")
    text = re.sub(r"[*_`#>\\]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def _markdown_table_at(source: str, header: str) -> str:
    """Đọc nguyên khối Markdown từ dòng đầu, giữ cả ô rỗng và hàng căn lề."""

    lines = source.splitlines()
    start = lines.index(header)

    rows: list[str] = []
    while start < len(lines) and lines[start].startswith("|"):
        rows.append(lines[start])
        start += 1
    return "\n".join(rows)


@pytest.fixture(scope="session")
def source_text() -> str:
    parts = [
        (PROJECT_ROOT / "references" / name).read_text(encoding="utf-8")
        for name in SOURCE_FILES
    ]
    return _normalise("\n".join(parts))


def _children(graph) -> dict:
    kids: dict = {}
    for child, _, parent in graph.triples((None, URIRef(ONTOLOGY_NS + "partOf"), None)):
        kids.setdefault(parent, []).append(child)
    return kids


def _leaves(graph) -> list:
    """Phần văn bản không còn phần con nào.

    Chỉ những phần này mới là một đoạn liền mạch trong công văn. Phần có con thì
    nguyên văn của nó được ghép lại từ các con — trong đó có bảng đã bị làm phẳng
    thành text thuần — nên không so khớp từng chữ với nguồn được.
    """

    kids = _children(graph)
    official = URIRef(ONTOLOGY_NS + "officialText")
    in_document = URIRef(ONTOLOGY_NS + "inDocument")
    checked = {ONTOLOGY_NS + name for name in TEXT_SOURCED_DOCUMENTS}

    table_classes = {
        URIRef(ONTOLOGY_NS + "DocumentTable"),
        URIRef(ONTOLOGY_NS + "CertificateConversionTable"),
    }
    return [
        node
        for node in graph.subjects(official, None)
        if not kids.get(node)
        and not any((node, RDF.type, table) in graph for table in table_classes)
        and any(str(d) in checked for d in graph.objects(node, in_document))
    ]


def test_every_leaf_provision_is_copied_verbatim(ontology_graph, source_text) -> None:
    """Khoản và điểm phải nằm nguyên văn trong công văn."""

    official = URIRef(ONTOLOGY_NS + "officialText")
    leaves = _leaves(ontology_graph)
    assert leaves, "không tìm thấy phần văn bản lá nào"

    # Duyệt MỌI giá trị chứ không chỉ giá trị đầu: một câu bịa thêm vào cùng node
    # sẽ lọt nếu chỉ kiểm giá trị đầu tiên.
    drifted = sorted(
        str(node).rsplit("#", 1)[-1]
        for node in leaves
        for text in ontology_graph.objects(node, official)
        if _normalise(text) not in source_text
    )

    assert drifted == []


def test_all_tables_are_copied_cell_for_cell_from_their_sources(ontology_graph) -> None:
    """Cả 14 bảng trả lời phải khớp nguồn từng ký tự và đúng một giá trị."""

    verbatim_table = URIRef(ONTOLOGY_NS + "verbatimTableText")
    document_table = URIRef(ONTOLOGY_NS + "DocumentTable")
    conversion_table = URIRef(ONTOLOGY_NS + "CertificateConversionTable")

    mismatches = []
    for local_name, (source_name, header) in VERBATIM_TABLE_SOURCES.items():
        node = URIRef(ONTOLOGY_NS + local_name)
        source = (PROJECT_ROOT / "references" / source_name).read_text(encoding="utf-8")
        expected = _markdown_table_at(source, header)
        actual = list(ontology_graph.objects(node, verbatim_table))
        if (
            not any(
                (node, RDF.type, table_class) in ontology_graph
                for table_class in (document_table, conversion_table)
            )
            or len(actual) != 1
            or str(actual[0]) != expected
        ):
            mismatches.append(local_name)

    actual_tables = set(ontology_graph.subjects(verbatim_table, None))
    expected_tables = {
        URIRef(ONTOLOGY_NS + local_name) for local_name in VERBATIM_TABLE_SOURCES
    }
    assert actual_tables == expected_tables
    assert mismatches == []


def test_no_provision_diverges_from_its_own_subdivisions(ontology_graph) -> None:
    """MỌI cấp văn bản: nguyên văn của con phải nằm nguyên trong nguyên văn của cha.

    Giữ nội dung ở nhiều mức là có chủ đích - "Điều 24 nói gì" và "khoản 3 Điều 24
    ghi gì" là hai câu hỏi khác nhau, và nguyên văn của cha còn mang câu dẫn mà
    không con nào có ("... SV được xếp năm đào tạo như sau:"). Rủi ro thật không
    phải việc lặp mà là hai mức LỆCH NHAU khi cập nhật: sửa một điểm mà quên sửa
    khoản chứa nó thì chatbot tự mâu thuẫn, tuỳ người dùng hỏi ở cấp nào.

    Bản trước chỉ canh Điều -> Khoản (111 cặp) và bỏ trống Khoản -> Điểm (108),
    Phụ lục -> Bảng (10), Khoản -> Bảng (3). Tức là hơn nửa số cặp không ai canh,
    trong đó có đúng cấp chi tiết nhất và hay phải sửa nhất.
    """

    official = URIRef(ONTOLOGY_NS + "officialText")
    kids = _children(ontology_graph)

    textual = set(ontology_graph.subjects(official, None))
    expected_pairs = {
        (child, parent)
        for child, _, parent in ontology_graph.triples(
            (None, URIRef(ONTOLOGY_NS + "partOf"), None)
        )
        if child in textual and parent in textual
    }
    checked_pairs = set()
    drifted = []
    for parent, children in kids.items():
        whole = _normalise(next(ontology_graph.objects(parent, official), ""))
        if not whole:
            continue
        for child in children:
            part = _normalise(next(ontology_graph.objects(child, official), ""))
            if not part:
                continue
            checked_pairs.add((child, parent))
            if part not in whole:
                drifted.append(
                    f"{str(child).rsplit('#', 1)[-1]} ⊄ {str(parent).rsplit('#', 1)[-1]}"
                )

    assert sorted(drifted) == []
    assert expected_pairs, "không có cặp partOf nào mang nguyên văn ở cả hai cấp"
    assert checked_pairs == expected_pairs


def test_no_provision_carries_two_different_texts(ontology_graph) -> None:
    """Một phần văn bản chỉ được mang đúng một nguyên văn.

    Bản ontology trước gộp quyết định ban hành với quy chế kèm theo, nên "Điều 1"
    mang cùng lúc hai đoạn văn của hai tài liệu khác nhau và trả lời mâu thuẫn.
    """

    official = URIRef(ONTOLOGY_NS + "officialText")
    doubled = sorted(
        str(node).rsplit("#", 1)[-1]
        for node in set(ontology_graph.subjects(official, None))
        if len(list(ontology_graph.objects(node, official))) > 1
    )

    assert doubled == []


def test_every_document_part_can_be_traced_to_its_source(ontology_graph) -> None:
    """Mỗi phần văn bản tự nói ra nó ở đâu và tra bản gốc chỗ nào.

    Người hỏi không biết "Quyết định 1052" là văn bản gì, nên trích dẫn phải nêu
    số quyết định lẫn ngày ban hành, và kèm đường dẫn để tự kiểm chứng.
    """

    citation = URIRef(ONTOLOGY_NS + "citationLabel")
    url = URIRef(ONTOLOGY_NS + "documentUrl")

    missing = []
    for node in ontology_graph.subjects(URIRef(ONTOLOGY_NS + "officialText"), None):
        label = next(ontology_graph.objects(node, citation), None)
        link = next(ontology_graph.objects(node, url), None)
        if label is None or link is None or not str(link).startswith("https://"):
            missing.append(str(node).rsplit("#", 1)[-1])

    assert sorted(missing) == []


def test_every_number_appears_in_the_passage_it_cites(ontology_graph) -> None:
    """Node khẳng định một CON SỐ thì nguồn nó dẫn phải chứa đúng con số đó.

    Đây là phép kiểm sinh ra từ một lỗi thật, tìm ra ngày 15/8/2026: sáu mức học
    bổng khẳng định 5.000.000 đến 8.640.000 đồng nhưng dẫn nguồn về Điều 1 và
    Điều 2 QĐ317 - hai câu dẫn kết thúc bằng "cụ thể như sau:" và KHÔNG chứa số
    nào, vì cái bảng đứng sau chúng chưa bao giờ được nạp. Cả 321 phép kiểm lúc
    đó đều xanh: trích dẫn có mặt, có ngày, có đường dẫn, chỉ là trỏ nhầm chỗ.

    Vì sao canh riêng CON SỐ chứ không canh cả câu chữ: so bằng tỉ lệ từ trùng
    nhau là cái bẫy dự án đã vấp ba lần - nó chấm ``currencyCode "VND"`` là sai
    vì công văn viết "đồng", chấm ``performedBy Sinh viên`` là sai vì công văn
    viết "SV". Con số thì chuẩn hoá được không mơ hồ: bỏ hết dấu chấm, dấu phẩy
    và khoảng trắng rồi so chuỗi chữ số.

    Bỏ qua số dưới hai chữ số vì chúng trùng ngẫu nhiên với mọi thứ, và chấp
    nhận cả ``downloadUrl`` làm nguồn vì tên tệp biểu mẫu mang số hiệu của nó.
    """

    digits = re.compile(r"[^0-9]")
    numeric = re.compile(r"^\d+([.,]\d+)?$")
    based_on = URIRef(ONTOLOGY_NS + "basedOn")
    text_predicates = (
        URIRef(ONTOLOGY_NS + "officialText"),
        URIRef(ONTOLOGY_NS + "verbatimTableText"),
    )
    download_url = URIRef(ONTOLOGY_NS + "downloadUrl")

    unsourced = []
    for node in sorted(set(ontology_graph.subjects(based_on, None)), key=str):
        passage = "".join(
            str(value)
            for source in ontology_graph.objects(node, based_on)
            for predicate in text_predicates
            for value in ontology_graph.objects(source, predicate)
        )
        links = "".join(
            str(value) for value in ontology_graph.objects(node, download_url)
        )
        haystack = digits.sub("", passage) + " " + digits.sub("", links)
        for predicate, value in ontology_graph.predicate_objects(node):
            if not isinstance(value, Literal):
                continue
            raw = str(value).strip()
            if not numeric.match(raw):
                continue
            needle = digits.sub("", raw)
            if len(needle) < 2 or needle in haystack:
                continue
            unsourced.append(
                (
                    str(node).rsplit("#", 1)[-1],
                    str(predicate).rsplit("#", 1)[-1],
                    raw,
                )
            )

    assert sorted(unsourced) == []
