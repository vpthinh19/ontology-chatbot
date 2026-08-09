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
        ("Regulation1052Article24", "Điều 24"),
        ("Regulation1052Article24Clause03", "khoản 3 Điều 24"),
        ("Regulation1052Article24Clause01PointA", "điểm a khoản 1 Điều 24"),
        ("Regulation1052ChapterIV", "Chương IV"),
        ("TemporaryAcademicLeaveProcedure", "bảo lưu"),
        ("Form09TemporaryLeave", "Mẫu số 09"),
        ("Accounting", "Kế toán"),
    ],
)
def test_entities_are_named_the_way_a_student_would(graph, anchor, expected) -> None:
    """Phần văn bản gọi bằng số hiệu, thực thể có tên gọi bằng chính tên của nó."""

    assert expected in mentions(graph, anchor)


def test_every_anchor_keeps_at_least_one_unambiguous_mention(graph, anchors) -> None:
    """Không neo nào được mất hết cách gọi sau khi phân giải mơ hồ.

    ``mention_index`` tự ném lỗi nếu có neo trắng, nên test này chốt lại hợp đồng
    đó và đồng thời canh số lượng: nếu bộ rút gọn hỏng, tổng cách gọi sẽ tụt.
    """

    resolved, _ = mention_index(graph, anchors)

    assert set(resolved) == set(anchors)
    assert all(resolved[anchor] for anchor in anchors)
    assert sum(len(texts) for texts in resolved.values()) >= 700


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
    """Ba tài liệu đều có Điều 1; cách gọi phải nêu rõ tài liệu nào."""

    resolved, _ = mention_index(graph, anchors)

    assert "Điều 1 Quyết định 1052" in resolved["Decision1052Article01"]
    assert "Điều 1 Quyết định 729" in resolved["Decision729Article01"]
    assert "Điều 1 Quy chế đào tạo" in resolved["Regulation1052Article01"]
    # Điều 24 chỉ có ở quy chế nên không cần nêu tài liệu.
    assert "Điều 24" in resolved["Regulation1052Article24"]


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
    assert "đơn xin nghỉ học" in ambiguous


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


def test_overloaded_mentions_include_shared_article_numbers(graph, anchors) -> None:
    """Nguyên liệu câu từ chối phải gồm cả cách gọi ĐÃ gỡ được bằng bổ ngữ.

    ``mention_index`` cứu "Điều 1" bằng cách thêm tên tài liệu, nên nó biến mất
    khỏi bảng mơ hồ. Nhưng người dùng gõ đúng "Điều 1" mới là câu mơ hồ thật, và
    là ca từ chối sát thực tế nhất mà đồ thị sinh ra được.
    """

    overloaded = overloaded_mentions(graph, anchors)

    # KHÔNG chốt con số: mỗi công văn mới thêm vào ontology lại có "Điều 1" của
    # riêng nó, nên số này tăng theo thời gian một cách chính đáng. Cái phải giữ
    # là "Điều 1" bị nhiều tài liệu dùng chung, còn "Điều 24" thì không.
    assert len(overloaded["Điều 1"]) >= 3
    assert all(name.endswith("Article01") for name in overloaded["Điều 1"])
    assert "Điều 24" not in overloaded
    # Tờ đơn và mục tải của nó là MỘT thứ, không phải nguyên liệu từ chối.
    assert "Đơn xin chuyển trường" not in overloaded
