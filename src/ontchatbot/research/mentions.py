"""Một sinh viên nhắc tới thực thể này bằng những cách nào?

Đây là trục thứ nhất của bộ sinh dataset. Hai trục kia là khung ý định và phong
cách diễn đạt; ghép ba trục lại mới ra một câu hỏi.

Neo chia làm hai nhóm có cách gọi tên khác hẳn nhau:

* **Phần văn bản** (Điều, khoản, điểm, chương, phụ lục): cách gọi được dựng từ
  toạ độ của node để phản ánh cấu trúc tài liệu.
* **Thực thể có tên**: dùng nhãn chính, ``skos:altLabel`` và các phép rút gọn
  cơ học.

Ontology chỉ lưu các tên có nghĩa xác định; biến thể diễn đạt thuộc về dataset.
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
#: Tiền tố phân loại có thể bỏ khi tạo cách gọi rút gọn.
_DROPPED_PREFIXES = ("Thủ tục ", "Quy tắc ")
#: Tiền tố giao diện của nguồn không phải là một phần của cách gọi thực thể.
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

    # Một dạng chuẩn cho mỗi node; biến thể hoa/thường thuộc tầng phong cách.
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

    # Toạ độ phải kèm định danh tài liệu để không mơ hồ giữa các tài liệu có cùng
    # số điều. Mỗi phần văn bản có một cách gọi chuẩn để duy trì độ phủ dataset.
    short = _document_short_name(graph, node)
    found = [f"{coordinate} {short}"] if short else []
    if not found:
        label = next(graph.objects(node, RDFS.label), None)
        if label is not None:
            found.append(str(label))
    # Dùng toạ độ trần làm dự phòng; ``mention_index`` kiểm tra mọi trường hợp mơ hồ.
    return tuple(dict.fromkeys(found)) or (coordinate,)


def _named_entity(graph: Graph, node: URIRef) -> tuple[str, ...]:
    """Nhãn chính, các tên gọi thay thế, và vài phép rút gọn cơ học."""

    label = next(graph.objects(node, RDFS.label), None)
    raw: list[str] = [] if label is None else [str(label)]
    raw.extend(sorted(str(value) for value in graph.objects(node, SKOS.altLabel)))

    # Bỏ tiền tố giao diện trước khi tạo các cách gọi.
    found = [_without_artifact_prefix(text) for text in raw]
    for text in list(found):
        found.extend(_shortened(text))

    # Khử trùng theo chữ thường; khác biệt hoa/thường không tạo cách gọi mới.
    seen: dict[str, str] = {}
    for text in found:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if cleaned:
            seen.setdefault(cleaned.casefold(), cleaned)
    return tuple(seen.values())


def _without_artifact_prefix(text: str) -> str:
    """Bóc nhãn giao diện của nguồn và dấu câu sót lại ngay sau nó."""

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
            # Không tách tiếp tiền tố phân loại để tránh một cách gọi thiếu nghĩa.
            return [text[len(prefix) :]]

    parts = [_LEADING_PUNCTUATION.sub("", part).strip() for part in _SPLIT.split(text)]
    if len(parts) == 2 and all(len(part) >= 4 for part in parts):
        return parts
    return []


def overloaded_mentions(
    graph: Graph,
    local_names: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    """Cách gọi trỏ tới nhiều thực thể, kể cả khi có thể gỡ bằng bổ ngữ.

    Dùng cho nhóm câu từ chối, không dùng để sinh câu trả lời được. Các cách gọi
    này giữ nguyên mức mơ hồ của chúng, thay vì thêm bổ ngữ để phân giải.
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
    # Quy chế dùng số hiệu của quyết định ban hành. Tiền tố ``Quy chế`` phân biệt
    # quy chế với quyết định ban hành, là hai tài liệu riêng.
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
    """Kiểm tra các neo có cùng thực thể được mô hình hóa từ nhiều nguồn."""

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
    """Cách gọi đã phân giải, kèm danh sách cách gọi mơ hồ.

    Trả về hai thứ:

    * ``resolved`` - mỗi neo và các cách gọi chỉ trỏ tới đúng nó;
    * ``ambiguous`` - cách gọi trỏ tới nhiều neo, kèm danh sách các neo đó.

    Các cách gọi không phân giải được được dùng cho nhóm câu từ chối. Bổ ngữ chỉ
    được thêm khi nó phân biệt duy nhất thực thể.
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
            # Không lặp bổ ngữ đã có trong cách gọi.
            if qualifier is not None and qualifier.casefold() in text.casefold():
                qualifier = None
            # Chỉ dùng bổ ngữ nếu nó phân biệt được với mọi neo còn lại.
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
                # Khóa theo ``casefold`` để tránh các câu từ chối trùng nhau.
                ambiguous.setdefault(text.casefold(), set()).update(sharers)

    missing = sorted(name for name, texts in resolved.items() if not texts)
    if missing:
        raise ValueError(f"neo không còn cách gọi rõ nghĩa nào: {missing[:5]}")
    return (
        {name: tuple(texts) for name, texts in resolved.items()},
        {text: tuple(sorted(names)) for text, names in sorted(ambiguous.items())},
    )
