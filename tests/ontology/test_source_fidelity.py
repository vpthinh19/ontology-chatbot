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
from rdflib import RDF, OWL, URIRef

from ontchatbot.settings import ONTOLOGY_NS, PROJECT_ROOT

#: Công văn có bản sao dạng văn bản trong ``references/``.
#:
#: ``Qd317.md`` là bản OCR từ ảnh chụp công văn giấy, đã được đối chiếu lại với
#: chính bản scan: bộ OCR có thói quen **sửa lỗi của công văn** (tự thêm "trở
#: lên" vào chỗ bản gốc chỉ ghi "trở", tự bỏ chữ lặp "Trường Trường"). Đã hoàn
#: nguyên về đúng mặt chữ bản gốc - ontology trích dẫn công văn thật, không
#: trích dẫn bản đã được máy làm sạch.
SOURCE_FILES = ("Qd1052.md", "Qd729.md", "huong_dan_dong_hoc_phi.md", "Qd317.md")

#: Tài liệu lấy nội dung từ các tệp trên. Danh mục biểu mẫu không nằm đây vì
#: nguồn của nó là một trang web, chép về sẽ khác hình thức.
TEXT_SOURCED_DOCUMENTS = (
    "Decision1052",
    "Regulation1052",
    "Decision729",
    "TuitionPaymentGuidance",
    "Decision317",
)


def _normalise(text: str) -> str:
    """Bỏ khác biệt hình thức, giữ nguyên chữ."""

    text = unicodedata.normalize("NFC", str(text))
    text = re.sub(r"<br\s*/?>", " ", text).replace("&nbsp;", " ")
    text = re.sub(r"[*_`#>\\]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


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

    table = URIRef(ONTOLOGY_NS + "DocumentTable")
    return [
        node
        for node in graph.subjects(official, None)
        if not kids.get(node)
        and (node, RDF.type, table) not in graph
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

    checked = 0
    drifted = []
    for parent, children in kids.items():
        whole = _normalise(next(ontology_graph.objects(parent, official), ""))
        if not whole:
            continue
        for child in children:
            part = _normalise(next(ontology_graph.objects(child, official), ""))
            if not part:
                continue
            checked += 1
            if part not in whole:
                drifted.append(
                    f"{str(child).rsplit('#', 1)[-1]} ⊄ {str(parent).rsplit('#', 1)[-1]}"
                )

    assert sorted(drifted) == []
    # Nếu quan hệ partOf hỏng, phép duyệt trả về rỗng và test sẽ lặng lẽ xanh -
    # đúng kiểu hỏng nguy hiểm nhất. Chốt số cặp tối thiểu để nó phải đỏ.
    assert checked >= 200, f"chỉ kiểm được {checked} cặp cha-con, quan hệ partOf có vấn đề?"


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
