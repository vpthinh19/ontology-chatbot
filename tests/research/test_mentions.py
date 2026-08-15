"""Cách gọi tên thực thể phải rõ nghĩa, đủ tự nhiên, và không bịa."""

from __future__ import annotations

import pytest
from rdflib import URIRef

from ontchatbot.catalogue import load_catalogue
from ontchatbot.research.mentions import (
    _LEADING_PUNCTUATION,
    mention_index,
    mentions,
    overloaded_mentions,
)
from ontchatbot.runtime.sparql import load_ontology
from ontchatbot.settings import ONTOLOGY_NS, QUERY_CATALOGUE_PATH


@pytest.fixture(scope="module")
def graph():
    return load_ontology()


@pytest.fixture(scope="module")
def anchors() -> tuple[str, ...]:
    catalogue = load_catalogue(QUERY_CATALOGUE_PATH)
    found: set[str] = set()
    for spec in catalogue.values():
        if spec.tier != "primary":
            continue
        for slot in spec.slots.values():
            if slot.kind == "iri":
                found.update(value[1:] for value in slot.values)
    return tuple(sorted(found))


@pytest.mark.parametrize(
    ("anchor", "expected"),
    [
        # TOẠ ĐỘ PHẢI KÈM TÊN VĂN BẢN. "Điều 24" trơ trọi không chỉ về đâu cả -
        # mỗi quy chế đều có Điều 24 của riêng nó, nên tách khỏi văn bản thì
        # chương/điều/khoản đều vô nghĩa. Bản trước lấy toạ độ trần làm cách gọi
        # CHÍNH và bỏ qua ``rdfs:label`` vốn đã đầy đủ; nó chỉ chạy được vì đồ
        # thị tình cờ có mỗi một văn bản mang số đó.
        ("Regulation1052Article24", "Điều 24 Quy chế 1052"),
        ("Regulation626Article24", "Điều 24 Quy chế 626"),
        ("Regulation1052Article24Clause03", "khoản 3 Điều 24 Quy chế 1052"),
        ("Regulation1052Article24Clause01PointA", "điểm a khoản 1 Điều 24 Quy chế 1052"),
        ("Regulation1052ChapterIV", "Chương IV Quy chế 1052"),
        # Trước đây là "bảo lưu" trơ trọi. Đã bỏ khỏi ontology: QĐ1052 dùng từ
        # này ở năm ngữ cảnh khác nhau, nên một mình nó không trỏ được vào đâu.
        ("TemporaryAcademicLeaveProcedure", "bảo lưu kết quả"),
        ("Form09TemporaryLeave", "Mẫu số 09"),
        ("Accounting", "Kế toán"),
    ],
)
def test_entities_are_named_the_way_a_student_would(graph, anchor, expected) -> None:
    """Phần văn bản gọi bằng số hiệu, thực thể có tên gọi bằng chính tên của nó."""

    assert expected in mentions(graph, anchor)


def test_every_anchor_keeps_at_least_one_unambiguous_mention(graph, anchors) -> None:
    """Không neo nào được mất hết cách gọi sau khi phân giải mơ hồ.

    ``mention_index`` tự ném lỗi nếu có neo trắng; test này chốt lại
    hợp đồng thật: đúng toàn bộ neo được trả về và neo nào cũng có
    ít nhất một cách gọi không mơ hồ.
    """

    resolved, _ = mention_index(graph, anchors)

    assert set(resolved) == set(anchors)
    assert all(resolved[anchor] for anchor in anchors)


def test_a_mention_never_points_at_two_DIFFERENT_things(graph, anchors) -> None:
    """Cách gọi đã phân giải phải trỏ tới đúng một THỨ, không nhất thiết một neo.

    Đây là ràng buộc quan trọng nhất của module: dạy model rằng "Điều 1" ứng với
    một điều cụ thể, trong khi ba tài liệu đều có Điều 1, là dạy nó đoán bừa.

    Ngoại lệ duy nhất được phép là một thứ ngoài đời bị mô hình thành nhiều node.
    Một tờ đơn có mặt hai lần - bản theo quyết định và mục tải trên web, nối bằng
    ``catalogueEntryForForm``. Bắt cách gọi phải trỏ một node sẽ khiến câu hỏi tự
    nhiên nhất về biểu mẫu bị từ chối, mà nó KHÔNG hề mơ hồ với người hỏi.
    """

    resolved, _ = mention_index(graph, anchors)

    owners: dict[str, set[str]] = {}
    for anchor, texts in resolved.items():
        for text in texts:
            owners.setdefault(text.casefold(), set()).add(anchor)

    shared = {text: names for text, names in owners.items() if len(names) > 1}
    link = URIRef(ONTOLOGY_NS + "catalogueEntryForForm")
    for text, names in shared.items():
        nodes = {URIRef(ONTOLOGY_NS + name) for name in names}
        assert all(
            any(other in nodes for other in graph.objects(node, link))
            or any(other in nodes for other in graph.subjects(link, node))
            for node in nodes
        ), f"{text!r} trỏ tới nhiều thứ KHÁC NHAU: {sorted(names)}"


def test_article_numbers_shared_by_documents_are_qualified(graph, anchors) -> None:
    """Số hiệu điều trùng nhau thì cách gọi phải nêu rõ tài liệu nào.

    Có hai trục trùng, và bổ ngữ phải gỡ được cả hai:

    * quyết định ban hành với quy chế kèm theo nó - cả hai đều có Điều 1;
    * hai ĐỜI quy chế - cả hai đều có Điều 10, mà bản 2025 nói về xoá lớp học
      phần còn bản 2021 nói về rút bớt học phần đã đăng ký.

    Trục thứ hai từng lọt lưới: bổ ngữ lấy bốn từ đầu của nhãn tài liệu, mà bốn
    từ đầu của cả hai quy chế đều là "Quy chế đào tạo trình độ".
    """

    resolved, _ = mention_index(graph, anchors)

    assert "Điều 1 Quyết định 1052" in resolved["Decision1052Article01"]
    assert "Điều 1 Quy chế 1052" in resolved["Regulation1052Article01"]
    assert "Điều 10 Quy chế 1052" in resolved["Regulation1052Article10"]
    assert "Điều 10 Quy chế 753" in resolved["Regulation753Article10"]
    # Điều 24 nay có ở cả hai quy chế, nên phải nêu rõ nguồn.
    assert "Điều 24 Quy chế 1052" in resolved["Regulation1052Article24"]
    assert "Điều 24 Quy chế 626" in resolved["Regulation626Article24"]


def test_ambiguous_mentions_are_reported_for_the_rejection_class(graph, anchors) -> None:
    """Cách gọi mơ hồ không bị vứt đi - nó là nguyên liệu câu từ chối.

    ``docs/CONCEPT.md``: câu quá mơ hồ để có một câu trả lời đúng duy nhất thì
    phải bị từ chối. Sinh nhóm này từ đồ thị thật thì không phải bịa.
    """

    _, ambiguous = mention_index(graph, anchors)

    assert ambiguous
    assert all(len(owners) > 1 for owners in ambiguous.values())
    # Bảng mơ hồ khoá theo dạng casefold: "Đơn xin nghỉ học" và "đơn xin nghỉ
    # học" là MỘT cách gọi, tách đôi sẽ đếm thừa và sinh câu từ chối trùng nhau.
    assert all(text == text.casefold() for text in ambiguous)
    # Các diện miễn học phần đã được gộp về bảng nguyên văn, nên ví dụ còn sống
    # là số mẫu xuất hiện ở cả văn bản biểu mẫu và mục tải tương ứng.
    assert "mẫu số 13" in ambiguous


def test_forms_are_not_ambiguous_with_their_own_download_entry(graph, anchors) -> None:
    """Tờ đơn và mục tải của chính nó KHÔNG được tính là hai thứ khác nhau.

    Chín tờ đơn nằm trong ontology hai lần. Coi chúng là mơ hồ đã dạy chatbot từ
    chối *"Đơn xin chuyển trường là mẫu số mấy"* - câu hỏi tự nhiên nhất về biểu
    mẫu - trong khi dạng có tiền tố *"Mẫu số 13 - ..."* thì trả lời bình thường.
    """

    resolved, ambiguous = mention_index(graph, anchors)

    assert "Đơn xin chuyển trường" in resolved["Form13UniversityTransfer"]
    assert "Đơn xin chuyển trường" in resolved["FormCatalogueEntry013"]
    assert "đơn xin chuyển trường" not in ambiguous
    assert "đơn xin chuyển ngành" not in ambiguous


def test_download_entries_never_keep_the_web_ui_prefix(graph, anchors) -> None:
    """"Mục tải:" là nhãn giao diện của trang web, không phải cách ai gọi tờ đơn.

    Giữ nó sinh ra *"Mục tải: Đơn xin hoãn thi tương ứng mẫu số mấy hả?"*, và vì
    luật chọn tên ưu tiên tên DÀI cho giọng trang trọng nên chính giọng trang
    trọng dính nhiều nhất.
    """

    resolved, _ = mention_index(graph, anchors)
    every = [text for texts in resolved.values() for text in texts]

    assert not [text for text in every if text.startswith("Mục tải")]
    assert not [text for text in every if _LEADING_PUNCTUATION.match(text)]


def test_document_coordinates_are_never_raw_rejection_material(graph, anchors) -> None:
    """Toạ độ văn bản không đủ nghĩa không được sinh ở bất kỳ nhánh nào.

    ``mention_index`` chỉ nhận cách gọi kèm tài liệu, nên ``overloaded_mentions``
    cũng không được khôi phục "Điều 1" làm nguyên liệu câu từ chối. Một toạ độ
    trần không phải câu hỏi mơ hồ: nó không định vị được văn bản nào để hỏi.
    """

    resolved, _ = mention_index(graph, anchors)
    overloaded = overloaded_mentions(graph, anchors)

    assert "Điều 1" not in {
        text for texts in resolved.values() for text in texts
    }
    assert "Điều 1" not in overloaded
    assert "Điều 24" not in overloaded
    # Tờ đơn và mục tải của nó là MỘT thứ, không phải nguyên liệu từ chối.
    assert "Đơn xin chuyển trường" not in overloaded
