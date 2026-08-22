"""Kho thẻ tra cứu: mỗi thẻ là một câu trả lời mà hệ thống có thể đưa ra.

Một thẻ gồm hai phần. Phần *chữ* lấy từ ontology - nhãn tiếng Việt của thực thể,
các tên gọi khác, toạ độ văn bản, nhãn của mục cha; đây là thứ được mã hoá thành
vector rồi đem so với câu hỏi. Phần *truy vấn* lấy từ danh mục truy vấn, bằng
cách điền IRI của thực thể vào khuôn SPARQL tương ứng.

Cả hai phần đều sinh tự động, nên thêm một thực thể vào ontology chỉ cần nạp lại
kho thẻ - không phải huấn luyện lại mô hình.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from string import Template

import rdflib
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from ..settings import ONTOLOGY_PATH, QUERY_CATALOGUE_PATH

_IRI = re.compile(r"(?<![\w:])(:[A-Z][A-Za-z0-9_]*)")

REFUSAL_QUERY_ID = "no-information"
REFUSAL_MARKER = "không có thông tin"
REFUSAL_TEXT = "câu hỏi ngoài phạm vi dữ liệu học vụ"


@dataclass(frozen=True)
class Card:
    """Một câu trả lời có thể đưa ra, mô tả bằng chữ và bằng truy vấn."""

    query_id: str
    anchors: tuple[str, ...]
    text: str
    query: str

    @property
    def is_refusal(self) -> bool:
        return self.query_id == REFUSAL_QUERY_ID


def load_graph(path: Path = ONTOLOGY_PATH) -> rdflib.Graph:
    graph = rdflib.Graph()
    graph.parse(path, format="turtle")
    return graph


def _namespace(graph: rdflib.Graph) -> str:
    base = dict(graph.namespaces()).get("")
    if base is None:
        raise ValueError("ontology không khai báo prefix mặc định ':'")
    return str(base)


def _shorten(term, base: str) -> str:
    text = str(term)
    return ":" + text[len(base) :] if text.startswith(base) else text


def _literals(graph: rdflib.Graph, subject, predicate) -> list[str]:
    """Literal của một thuộc tính, SẮP XẾP để không phụ thuộc thứ tự duyệt.

    rdflib không bảo đảm thứ tự trả về, mà phần chữ của thẻ phải giống hệt nhau
    giữa lúc huấn luyện và lúc phục vụ thì vector mới trùng.
    """
    return sorted(
        str(value)
        for value in graph.objects(subject, predicate)
        if isinstance(value, rdflib.Literal)
    )


def entity_texts(graph: rdflib.Graph) -> dict[str, list[str]]:
    """Các cụm chữ mô tả từng cá thể có tên, xếp từ cụ thể tới khái quát."""
    base = _namespace(graph)
    namespace = rdflib.Namespace(base)
    texts: dict[str, str] = {}

    for subject in graph.subjects(RDF.type, OWL.NamedIndividual):
        parts: list[str] = _literals(graph, subject, RDFS.label)[:1]
        parts += _literals(graph, subject, SKOS.altLabel)

        for predicate, prefix in (
            (namespace.articleNumber, "Điều"),
            (namespace.clauseNumber, "khoản"),
            (namespace.pointLetter, "điểm"),
        ):
            parts += [f"{prefix} {value}" for value in _literals(graph, subject, predicate)]

        parts += _literals(graph, subject, namespace.headingText)

        # Nhãn cha và nhãn lớp được sắp xếp: rdflib không bảo đảm thứ tự duyệt,
        # mà phần chữ của thẻ phải giống hệt nhau giữa lúc huấn luyện và lúc
        # phục vụ thì vector mới trùng.
        parents: set[str] = set()
        for predicate in (namespace.partOf, namespace.inDocument):
            for parent in graph.objects(subject, predicate):
                parents.update(
                    _literals(graph, parent, RDFS.label)
                    or [_shorten(parent, base).lstrip(":")]
                )
        parts += sorted(parents)

        classes: set[str] = set()
        for class_term in graph.objects(subject, RDF.type):
            if class_term == OWL.NamedIndividual:
                continue
            classes.update(
                _literals(graph, class_term, RDFS.label)
                or [_shorten(class_term, base).lstrip(":")]
            )
        parts += sorted(classes)

        cleaned = [part.strip() for part in parts if part and part.strip()]
        texts[_shorten(subject, base)] = list(dict.fromkeys(cleaned))

    return texts


def _class_labels(graph: rdflib.Graph) -> dict[str, list[str]]:
    """Nhãn của các lớp, dùng để phân biệt hai truy vấn trên cùng thực thể."""
    base = _namespace(graph)
    labels: dict[str, list[str]] = defaultdict(list)
    for class_term in graph.subjects(RDF.type, OWL.Class):
        name = _shorten(class_term, base)
        labels[name] += _literals(graph, class_term, RDFS.label)
    return labels


def build_cards(
    graph: rdflib.Graph | None = None,
    catalogue_path: Path = QUERY_CATALOGUE_PATH,
) -> list[Card]:
    """Bung danh mục truy vấn thành kho thẻ, kèm một thẻ từ chối."""
    graph = graph if graph is not None else load_graph()
    texts = entity_texts(graph)
    class_labels = _class_labels(graph)

    cards: list[Card] = []
    with open(catalogue_path, encoding="utf-8") as handle:
        entries = [json.loads(line) for line in handle if line.strip()]

    for entry in entries:
        template = entry["target_template"]
        slots = entry.get("slots") or {}
        if not slots:
            fillings = [({}, ())]
        else:
            (name, slot), = slots.items()
            fillings = [({name: value}, (value,)) for value in slot["values"]]

        for mapping, _ in fillings:
            query = Template(template).substitute(mapping) if mapping else template
            query = " ".join(query.split())
            # Khuôn không có slot thì IRI nằm sẵn trong câu truy vấn, và một câu
            # trả lời có thể neo vào nhiều thực thể, nên lấy neo từ chính chuỗi.
            anchors = tuple(sorted({name for name in _IRI.findall(query) if name in texts}))
            described = [part for iri in anchors for part in texts[iri]]
            # Cùng một thực thể có thể được hỏi theo nhiều khía cạnh; khía cạnh
            # nằm ở lớp mà truy vấn nhắc tới, nên nhãn lớp cũng vào phần chữ.
            # So theo TOKEN IRI, không phải chuỗi con: ":FormCatalogueEntry005"
            # không được kéo theo lớp ":FormCatalogue".
            mentioned = {name for name in _IRI.findall(query)}
            aspects = [
                label
                for name in sorted(mentioned - set(texts))
                for label in class_labels.get(name, ())
            ]
            # Thẻ từ chối không neo vào thực thể nào, nên phần chữ của nó được
            # viết thẳng thay vì lấy từ ontology.
            # Khử trùng ở mức thẻ: nhãn lớp có thể đến từ cả node lẫn khía cạnh,
            # và hai neo trong cùng một thẻ thường dùng chung nhãn cha.
            text = (
                REFUSAL_TEXT
                if entry["query_id"] == REFUSAL_QUERY_ID
                else " | ".join(dict.fromkeys([*described, *aspects]))
            )
            cards.append(
                Card(
                    query_id=entry["query_id"],
                    anchors=anchors,
                    text=text,
                    query=query,
                )
            )

    if not any(card.is_refusal for card in cards):
        raise ValueError("danh mục truy vấn thiếu mục từ chối")
    return cards


class CardLookup:
    """Tra thẻ theo nhãn của dataset, tức cặp (query_id, danh sách IRI).

    Dataset ghi đích bằng IRI chứ không bằng chuỗi SPARQL, vì chuỗi ấy suy ra
    được từ danh mục truy vấn. Lớp này là chỗ duy nhất thực hiện phép suy đó,
    nên khuôn truy vấn đổi thì dataset không phải sửa theo.
    """

    def __init__(self, cards: list[Card] | None = None) -> None:
        self._cards = cards if cards is not None else build_cards()
        self._by_key = {(card.query_id, card.anchors): card for card in self._cards}

    @property
    def cards(self) -> list[Card]:
        return self._cards

    def card(self, query_id: str, target) -> Card:
        key = (query_id, tuple(target or ()))
        try:
            return self._by_key[key]
        except KeyError:
            raise KeyError(f"không có thẻ cho {key}") from None

    def query(self, query_id: str, target) -> str:
        """Chuỗi SPARQL ứng với nhãn của một dòng dataset."""
        return self.card(query_id, target).query
