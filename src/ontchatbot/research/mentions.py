"""Một sinh viên nhắc tới thực thể này bằng những cách nào?

Đây là trục thứ nhất của bộ sinh dataset. Hai trục kia là khung ý định và phong
cách diễn đạt; ghép ba trục lại mới ra một câu hỏi.

Neo chia làm hai nhóm có cách gọi tên khác hẳn nhau:

* **Phần văn bản** (Điều, khoản, điểm, chương, phụ lục) - 280 neo, không neo nào
  có ``skos:altLabel`` và cũng không cần: người ta gọi chúng bằng SỐ HIỆU. Nhãn
  đầy đủ *"khoản 3 Điều 24 Quy chế đào tạo trình độ đại học"* không phải cách ai
  gõ vào ô chat. Cách gọi được dựng lại từ chính toạ độ của node nên không thể
  lệch với cấu trúc thật.
* **Thực thể có tên** - nhãn ĐÃ LÀ cách người ta gọi (*"Kế toán"*, *"Kỹ thuật
  nhiệt"*). Thêm ``skos:altLabel`` khi có, cộng vài phép rút gọn cơ học.

Ontology cố ý KHÔNG chứa biến thể khẩu ngữ - ``docs/ONTOLOGY.md`` cấm nhồi
``altLabel`` cho đủ chỉ tiêu, vì tên lỏng nghĩa sẽ dạy chatbot trả lời sai một
cách tự tin. Biến thể diễn đạt thuộc về dataset, và đó là việc của module này.
"""

from __future__ import annotations

import re

from rdflib import RDFS, SKOS, Graph, URIRef

from ..settings import ONTOLOGY_NS
from .answer_scope import rdf_type_names

#: Nhãn thực thể hay có dạng "tiền tố - nội dung" hoặc "tiền tố: nội dung".
#: Nhận cả gạch nối ngắn lẫn gạch dài: nguồn công văn dùng lẫn lộn hai loại, và
#: nhãn nào dùng gạch dài mà không tách được sẽ đi thẳng vào câu hỏi nguyên khối.
_SPLIT = re.compile(r"\s+[-‐-―]\s+|:\s+")
#: Tiền tố phân loại mà người hỏi thường bỏ đi, nhưng dạng đầy đủ VẪN là cách gọi
#: tự nhiên: "Thủ tục nghỉ học tạm thời" là câu người ta thật sự nói.
_DROPPED_PREFIXES = ("Thủ tục ", "Quy tắc ")
#: Tiền tố là NHÃN GIAO DIỆN của nguồn, không phải cách gọi. Không ai hỏi "Mục
#: tải: Đơn xin hoãn thi tương ứng mẫu số mấy" - giữ dạng đầy đủ chỉ sinh ra câu
#: không người dùng nào gõ, mà lại dính nhiều nhất ở giọng trang trọng vì luật
#: chọn tên ưu tiên tên dài.
_ARTIFACT_PREFIXES = ("Mục tải: ",)
#: Dấu câu sót lại ở đầu nhãn sau khi bóc tiền tố.
_LEADING_PUNCTUATION = re.compile(r"^[^\wÀ-ỹ]+")


def mentions(graph: Graph, local_name: str) -> tuple[str, ...]:
    """Các cách gọi một thực thể, theo thứ tự ổn định và không trùng nhau."""

    node = URIRef(ONTOLOGY_NS + local_name)
    classes = rdf_type_names(graph, node)
    coordinates = _document_coordinates(graph, node, classes)
    if coordinates:
        return coordinates
    return _named_entity(graph, node)


def _document_coordinates(
    graph: Graph,
    node: URIRef,
    classes: frozenset[str],
) -> tuple[str, ...]:
    """Cách gọi một phần văn bản, dựng từ toạ độ của chính nó.

    Trả về rỗng nếu node không phải phần văn bản đánh số được.
    """

    def value(name: str) -> str | None:
        found = next(graph.objects(node, URIRef(ONTOLOGY_NS + name)), None)
        return str(found) if found is not None else None

    article = value("articleNumber")
    clause = value("clauseNumber")
    point = value("pointLetter")
    chapter = value("chapterNumber")
    appendix = value("appendixNumber")

    # Một dạng chuẩn cho mỗi node, KHÔNG sinh biến thể hoa/thường ở đây: viết hoa
    # hay không là chuyện của phong cách diễn đạt, và trộn hai tầng vào nhau sẽ
    # khiến cùng một node trông như hai cách gọi khác nhau.
    if "Point" in classes and point and clause and article:
        coordinate = f"điểm {point} khoản {clause} Điều {article}"
    elif "Clause" in classes and clause and article:
        coordinate = f"khoản {clause} Điều {article}"
    elif "Article" in classes and article:
        coordinate = f"Điều {article}"
    elif "Chapter" in classes and chapter:
        coordinate = f"Chương {chapter}"
    elif "Appendix" in classes and appendix:
        coordinate = f"Phụ lục {appendix}"
    else:
        return ()

    # TOẠ ĐỘ TRẦN KHÔNG BAO GIỜ LÀ MỘT CÁCH GỌI. "Điều 12" tách khỏi văn bản thì
    # không chỉ về cái gì cả - mỗi quy chế đều có Điều 12 của riêng nó.
    #
    # Bản trước trả về đúng toạ độ trần và bỏ qua ``rdfs:label``, dù nhãn ấy vốn
    # đã đầy đủ ("Điều 10 Quy chế đào tạo trình độ đại học"). Nó CHẠY ĐƯỢC chỉ vì
    # đồ thị tình cờ có mỗi một văn bản mang số đó - đúng do may, không do thiết
    # kế. Nạp thêm Quy chế tuyển sinh là **111 cách gọi lật sang mơ hồ** cùng lúc,
    # kéo theo 609 dòng dataset đang dạy hỏi bằng toạ độ trần.
    #
    # Nay lấy chính nhãn làm cách gọi, cộng dạng ngắn theo số hiệu văn bản, vì
    # người hỏi dùng cả hai: "Điều 10 Quy chế đào tạo trình độ đại học" và
    # "Điều 10 Quy chế 1052".
    # MỘT cách gọi cho mỗi phần, không hai. Luật phủ bắt dạy TỪNG cặp (node, cách
    # gọi) ít nhất một lần, nên thêm một cách gọi là nhân đôi sàn dòng của cả
    # miền văn bản - đo thật: 533 phần văn bản thành 1.066 dòng bắt buộc, đẩy
    # dataset lên 6.083 và làm miền trọng tâm tụt từ 39,4% xuống 25,7%.
    #
    # Dùng dạng THEO SỐ HIỆU ("Điều 24 Quy chế 1052"), không dùng nhãn đầy đủ
    # ("Điều 24 Quy chế đào tạo trình độ đại học"). Cả hai đều đủ nghĩa, nhưng
    # dạng số hiệu dài 5 từ còn nhãn đầy đủ dài 9 - mà luật "mỗi miền trả lời
    # được phải có ít nhất 15% câu ngắn 2-6 từ" thì nhãn 9 từ KHÔNG BAO GIỜ sinh
    # nổi một câu ngắn. Đo thật: lấy nhãn đầy đủ thì miền văn bản chỉ còn 8,6%
    # câu ngắn, tức phải hạ hợp đồng - đúng thứ không được làm.
    #
    # Dạng số hiệu cũng là quy ước dự án đã dùng sẵn để gỡ mơ hồ, nên không đẻ
    # thêm khái niệm nào.
    short = _document_short_name(graph, node)
    found = [f"{coordinate} {short}"] if short else []
    if not found:
        label = next(graph.objects(node, RDFS.label), None)
        if label is not None:
            found.append(str(label))
    # Không còn cách nào định vị được văn bản thì thà giữ toạ độ trần còn hơn để
    # node mất sạch cách gọi - chốt chặn ở ``mention_index`` sẽ báo nếu nó mơ hồ.
    return tuple(dict.fromkeys(found)) or (coordinate,)


def _named_entity(graph: Graph, node: URIRef) -> tuple[str, ...]:
    """Nhãn chính, các tên gọi thay thế, và vài phép rút gọn cơ học."""

    label = next(graph.objects(node, RDFS.label), None)
    raw: list[str] = [] if label is None else [str(label)]
    raw.extend(sorted(str(value) for value in graph.objects(node, SKOS.altLabel)))

    # Tiền tố giao diện bị THAY THẾ chứ không bổ sung: giữ lại dạng đầy đủ nghĩa
    # là vẫn để nó lọt vào câu hỏi.
    found = [_without_artifact_prefix(text) for text in raw]
    for text in list(found):
        found.extend(_shortened(text))

    # Lọc trùng KHÔNG phân biệt hoa thường, giữ dạng gặp đầu tiên (là rdfs:label).
    # Vài thực thể có altLabel chỉ khác nhãn chính ở chữ hoa - giữ cả hai sẽ thành
    # hai "cách gọi" cho cùng một thứ, và phá vỡ ràng buộc mỗi cách gọi một neo.
    seen: dict[str, str] = {}
    for text in found:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if cleaned:
            seen.setdefault(cleaned.casefold(), cleaned)
    return tuple(seen.values())


def _without_artifact_prefix(text: str) -> str:
    """Bóc nhãn giao diện của nguồn, kèm dấu câu sót lại ngay sau nó.

    *"Mục tải: – Đơn xin chuyển ngành…"* để nguyên sẽ thành một cách gọi mở đầu
    bằng dấu gạch, và nó đã đi vào 41 dòng dataset.
    """

    for prefix in _ARTIFACT_PREFIXES:
        if text.startswith(prefix):
            return _LEADING_PUNCTUATION.sub("", text[len(prefix) :]).strip()
    return text


def _shortened(text: str) -> list[str]:
    """Rút gọn cơ học: bỏ tiền tố phân loại, tách nhãn ghép.

    *"Mẫu số 09 - Đơn xin nghỉ học tạm thời"* cho cả **"Mẫu số 09"** lẫn
    **"Đơn xin nghỉ học tạm thời"** - người hỏi dùng cả hai. Chỉ tách khi cả hai
    vế đều đủ dài để còn nghĩa; *"Điểm I"* tách ra sẽ thành **"I"**, vô nghĩa và
    trùng với hàng chục thứ khác.
    """

    for prefix in _DROPPED_PREFIXES:
        if text.startswith(prefix) and len(text) > len(prefix) + 3:
            # Tiền tố phân loại đứng riêng thì vô nghĩa và trùng nhau ở hàng chục
            # thực thể, nên KHÔNG tách tiếp phần đuôi.
            return [text[len(prefix) :]]

    parts = [_LEADING_PUNCTUATION.sub("", part).strip() for part in _SPLIT.split(text)]
    if len(parts) == 2 and all(len(part) >= 4 for part in parts):
        return parts
    return []


def overloaded_mentions(
    graph: Graph,
    local_names: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    """Cách gọi trỏ tới nhiều thực thể, KỂ CẢ khi gỡ được bằng bổ ngữ.

    Khác ``mention_index``: ở đó *"Điều 1"* được cứu bằng cách thêm tên tài liệu,
    nên nó biến mất khỏi danh sách mơ hồ. Nhưng người dùng gõ đúng *"Điều 1"* mới
    là câu mơ hồ thật, và là ca từ chối sát thực tế nhất mà đồ thị sinh ra được -
    ba tài liệu đều có Điều 1 với nội dung khác hẳn nhau.

    Dùng cho nhóm câu từ chối, không dùng để sinh câu trả lời được.
    """

    owners: dict[str, set[str]] = {}
    display: dict[str, str] = {}
    for name in local_names:
        for text in mentions(graph, name):
            key = text.casefold()
            owners.setdefault(key, set()).add(name)
            display.setdefault(key, text)
    return {
        display[key]: tuple(sorted(names))
        for key, names in sorted(owners.items())
        if len(names) > 1 and not _one_real_thing(graph, names)
    }


def _document_short_name(graph: Graph, node: URIRef) -> str | None:
    """Tên ngắn của tài liệu chứa node, dùng để phân biệt số hiệu trùng nhau."""

    document = next(graph.objects(node, URIRef(ONTOLOGY_NS + "inDocument")), None)
    if document is None:
        return None
    number = next(graph.objects(document, URIRef(ONTOLOGY_NS + "documentNumber")), None)
    if number is not None:
        return f"Quyết định {str(number).split('/', 1)[0]}"
    # Quy chế không mang số hiệu của riêng nó - nó được BAN HÀNH KÈM một quyết
    # định, và số hiệu quyết định là thứ phân biệt hai đời quy chế. Đi thêm một
    # chặng để lấy số đó.
    #
    # Trước đây chỗ này lấy bốn từ đầu của nhãn, và bốn từ đầu của cả hai quy chế
    # đều là "Quy chế đào tạo trình độ": chữ phân biệt "năm 2021" nằm tận cuối
    # nhãn. Hậu quả là "Điều 10" của hai đời quy chế cùng rút thành một cách gọi,
    # trong khi Điều 10 bản 2025 nói về xoá lớp học phần còn bản 2021 nói về rút
    # bớt học phần.
    #
    # Phải gọi là "Quy chế 1052" chứ KHÔNG phải "Quyết định 1052": quyết định ban
    # hành và quy chế kèm theo là hai tài liệu riêng, cả hai đều có Điều 1 với
    # nội dung khác hẳn nhau. Mượn nguyên tên quyết định thì gỡ được mơ hồ giữa
    # hai đời quy chế nhưng lại tạo mơ hồ mới giữa quy chế và quyết định của nó.
    issuer = next(graph.objects(document, URIRef(ONTOLOGY_NS + "issuedBy")), None)
    if issuer is not None:
        number = next(graph.objects(issuer, URIRef(ONTOLOGY_NS + "documentNumber")), None)
        if number is not None:
            return f"Quy chế {str(number).split('/', 1)[0]}"
    label = next(graph.objects(document, RDFS.label), None)
    return None if label is None else " ".join(str(label).split()[:4])


def _form_number_hint(graph: Graph, node: URIRef) -> str | None:
    """Phân biệt hai biểu mẫu trùng tiêu đề bằng chính số hiệu của chúng.

    Trang danh mục liệt kê *"Đơn xin chuyển Chương trình đào tạo"* hai lần, mẫu 5
    và mẫu 5A, trỏ về hai file khác nhau. Tiêu đề trùng nên mơ hồ thật, và cách
    người ta gỡ mơ hồ cũng chính là nói kèm số hiệu.
    """

    for name in ("listedFormNumber", "formNumber"):
        number = next(graph.objects(node, URIRef(ONTOLOGY_NS + name)), None)
        if number is not None:
            return f"mẫu số {number}"
    return None


def _one_real_thing(graph: Graph, names: set[str]) -> bool:
    """Các neo này có phải cùng MỘT thứ ngoài đời, chỉ được mô hình nhiều lần?

    Một tờ đơn nằm trong ontology hai lần: bản theo Quyết định 1052 và mục tải
    trên trang web, nối với nhau bằng ``catalogueEntryForForm``. Người hỏi *"Đơn
    xin chuyển trường là mẫu số mấy"* không hề mơ hồ - họ hỏi về một tờ đơn duy
    nhất. Coi đây là mơ hồ thì câu hỏi tự nhiên nhất về biểu mẫu bị TỪ CHỐI.

    Hai node vẫn giữ nguyên vì hai nguồn đánh số khác nhau (web ghi mẫu 11,
    quyết định ghi mẫu 13); chính KHUNG CÂU HỎI chọn node nào - họ hỏi số hiệu
    trên web đều mang chữ "trên web".
    """

    link = URIRef(ONTOLOGY_NS + "catalogueEntryForForm")
    nodes = {URIRef(ONTOLOGY_NS + name) for name in names}
    linked = {
        node
        for node in nodes
        if any(target in nodes for target in graph.objects(node, link))
        or any(source in nodes for source in graph.subjects(link, node))
    }
    return len(names) > 1 and linked == nodes


def mention_index(
    graph: Graph,
    local_names: tuple[str, ...],
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """Cách gọi ĐÃ PHÂN GIẢI, kèm danh sách cách gọi mơ hồ.

    Trả về hai thứ:

    * ``resolved`` - mỗi neo và các cách gọi chỉ trỏ tới đúng nó;
    * ``ambiguous`` - cách gọi trỏ tới nhiều neo, kèm danh sách các neo đó.

    Cái thứ hai KHÔNG phải rác cần bỏ đi. ``docs/CONCEPT.md`` quy định câu hỏi quá
    mơ hồ để có một câu trả lời đúng duy nhất thì phải bị TỪ CHỐI. Vậy nên đây
    chính là nguyên liệu tốt nhất cho nhóm câu từ chối "gần miền". Sinh chúng từ
    đồ thị thật thì không phải bịa, và bảo đảm chúng thực sự mơ hồ.

    "Điều 1" là ví dụ: ba tài liệu đều có Điều 1 với nội dung khác hẳn nhau. Nếu
    thêm được tên tài liệu để phân biệt thì dùng dạng đầy đủ; không thì cách gọi
    đó thuộc về nhóm từ chối.
    """

    raw = {name: mentions(graph, name) for name in local_names}

    owners: dict[str, set[str]] = {}
    for name, texts in raw.items():
        for text in texts:
            owners.setdefault(text.casefold(), set()).add(name)

    resolved: dict[str, list[str]] = {name: [] for name in local_names}
    ambiguous: dict[str, set[str]] = {}
    for name, texts in raw.items():
        node = URIRef(ONTOLOGY_NS + name)
        for text in texts:
            sharers = owners[text.casefold()]
            if len(sharers) == 1 or _one_real_thing(graph, sharers):
                resolved[name].append(text)
                continue
            qualifier = _document_short_name(graph, node) or _form_number_hint(graph, node)
            # Bổ ngữ đã nằm sẵn trong cách gọi thì không gỡ được mơ hồ, chỉ sinh
            # ra "Mẫu số 13 mẫu số 13". Trường hợp đó phải là câu từ chối.
            if qualifier is not None and qualifier.casefold() in text.casefold():
                qualifier = None
            # Bổ ngữ chỉ đáng dùng khi nó THẬT SỰ tách được các bên ra. Trước đây
            # chỗ này gắn bổ ngữ mà không kiểm, nên khi hai quy chế cùng cho ra
            # bổ ngữ "Quy chế đào tạo" thì cả hai đều nhận cùng một cách gọi và
            # mơ hồ vẫn nguyên - chỉ khác là nó không còn bị báo nữa.
            if qualifier is not None:
                others = {
                    _document_short_name(graph, URIRef(ONTOLOGY_NS + other))
                    or _form_number_hint(graph, URIRef(ONTOLOGY_NS + other))
                    for other in sharers
                    if other != name
                }
                if qualifier in others:
                    qualifier = None
            if qualifier is not None:
                resolved[name].append(f"{text} {qualifier}")
            else:
                # Khoá theo casefold: "Đơn xin nghỉ học" và "đơn xin nghỉ học" là
                # MỘT cách gọi, tách đôi sẽ đếm thừa và sinh câu từ chối trùng nhau.
                ambiguous.setdefault(text.casefold(), set()).update(sharers)

    missing = sorted(name for name, texts in resolved.items() if not texts)
    if missing:
        raise ValueError(f"neo không còn cách gọi rõ nghĩa nào: {missing[:5]}")
    return (
        {name: tuple(texts) for name, texts in resolved.items()},
        {text: tuple(sorted(names)) for text, names in sorted(ambiguous.items())},
    )
