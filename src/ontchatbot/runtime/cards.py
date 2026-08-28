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
import hashlib
from dataclasses import dataclass
from pathlib import Path
from string import Template

import pyoxigraph as ox

from ..settings import (
    CARD_CACHE_PATH,
    ONTOLOGY_NS,
    ONTOLOGY_PATH,
    QUERY_CATALOGUE_PATH,
)

_IRI = re.compile(r"(?<![\w:])(:[A-Z][A-Za-z0-9_]*)")

REFUSAL_QUERY_ID = "no-information"
REFUSAL_MARKER = "không có thông tin"
REFUSAL_TEXT = "câu hỏi ngoài phạm vi dữ liệu học vụ"

RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_LABEL = ox.NamedNode("http://www.w3.org/2000/01/rdf-schema#label")
SKOS_ALT_LABEL = ox.NamedNode("http://www.w3.org/2004/02/skos/core#altLabel")
OWL_CLASS = ox.NamedNode("http://www.w3.org/2002/07/owl#Class")
OWL_NAMED_INDIVIDUAL = ox.NamedNode("http://www.w3.org/2002/07/owl#NamedIndividual")


def _term(local_name: str) -> ox.NamedNode:
    return ox.NamedNode(ONTOLOGY_NS + local_name)


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


def subjects_of_type(store: ox.Store, class_term: ox.NamedNode) -> list:
    """Các chủ thể mang một lớp, xếp theo IRI để không phụ thuộc thứ tự duyệt."""

    return sorted(
        {
            quad.subject
            for quad in store.quads_for_pattern(None, RDF_TYPE, class_term)
        },
        key=lambda node: node.value,
    )


def objects(store: ox.Store, subject, predicate) -> list:
    """Mọi đối tượng của một cặp (chủ thể, thuộc tính)."""

    return [quad.object for quad in store.quads_for_pattern(subject, predicate, None)]


def _shorten(term, base: str = ONTOLOGY_NS) -> str:
    """IRI rút gọn về dạng ``:TenCucBo`` mà dataset và danh mục truy vấn dùng."""

    text = term.value
    return ":" + text[len(base) :] if text.startswith(base) else text


def _literals(store: ox.Store, subject, predicate) -> list[str]:
    """Literal của một thuộc tính, SẮP XẾP để không phụ thuộc thứ tự duyệt.

    Kho đồ thị không bảo đảm thứ tự trả về, mà phần chữ của thẻ phải giống hệt
    nhau giữa lúc huấn luyện và lúc phục vụ thì vector mới trùng.
    """
    return sorted(
        value.value
        for value in objects(store, subject, predicate)
        if isinstance(value, ox.Literal)
    )


def entity_texts(store: ox.Store) -> dict[str, list[str]]:
    """Các cụm chữ mô tả từng cá thể có tên, xếp từ cụ thể tới khái quát."""
    texts: dict[str, list[str]] = {}

    article_number = _term("articleNumber")
    clause_number = _term("clauseNumber")
    point_letter = _term("pointLetter")
    heading_text = _term("headingText")
    part_of = _term("partOf")
    in_document = _term("inDocument")

    for subject in subjects_of_type(store, OWL_NAMED_INDIVIDUAL):
        parts: list[str] = _literals(store, subject, RDFS_LABEL)[:1]
        parts += _literals(store, subject, SKOS_ALT_LABEL)

        for predicate, prefix in (
            (article_number, "Điều"),
            (clause_number, "khoản"),
            (point_letter, "điểm"),
        ):
            parts += [f"{prefix} {value}" for value in _literals(store, subject, predicate)]

        parts += _literals(store, subject, heading_text)

        # Nhãn cha và nhãn lớp được sắp xếp: kho đồ thị không bảo đảm thứ tự
        # duyệt, mà phần chữ của thẻ phải giống hệt nhau giữa lúc huấn luyện và
        # lúc phục vụ thì vector mới trùng.
        parents: set[str] = set()
        for predicate in (part_of, in_document):
            for parent in objects(store, subject, predicate):
                parents.update(
                    _literals(store, parent, RDFS_LABEL)
                    or [_shorten(parent).lstrip(":")]
                )
        parts += sorted(parents)

        classes: set[str] = set()
        for class_term in objects(store, subject, RDF_TYPE):
            if class_term == OWL_NAMED_INDIVIDUAL:
                continue
            classes.update(
                _literals(store, class_term, RDFS_LABEL)
                or [_shorten(class_term).lstrip(":")]
            )
        parts += sorted(classes)

        cleaned = [part.strip() for part in parts if part and part.strip()]
        texts[_shorten(subject)] = list(dict.fromkeys(cleaned))

    return texts


def _class_labels(store: ox.Store) -> dict[str, list[str]]:
    """Nhãn của các lớp, dùng để phân biệt hai truy vấn trên cùng thực thể."""
    labels: dict[str, list[str]] = defaultdict(list)
    for class_term in subjects_of_type(store, OWL_CLASS):
        labels[_shorten(class_term)] += _literals(store, class_term, RDFS_LABEL)
    return labels


def build_cards(
    store: ox.Store | None = None,
    catalogue_path: Path = QUERY_CATALOGUE_PATH,
) -> list[Card]:
    """Bung danh mục truy vấn thành kho thẻ, kèm một thẻ từ chối."""
    if store is None:
        from .sparql import load_ontology

        store = load_ontology()
    texts = entity_texts(store)
    class_labels = _class_labels(store)

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


#: Đổi số này khi hình dạng tệp đổi, để tệp cũ bị bỏ qua thay vì đọc sai.
CARD_CACHE_VERSION = 1


def _fingerprint(ontology_path: Path, catalogue_path: Path) -> str:
    """Mã băm của đúng hai tệp sinh ra bảng thẻ."""

    digest = hashlib.sha256()
    for path in (ontology_path, catalogue_path):
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def _read_cache(cache_path: Path, fingerprint: str) -> list[Card] | None:
    """Đọc bảng thẻ nướng sẵn, trả ``None`` nếu không dùng được vì bất cứ lẽ gì.

    Mọi đường hỏng đều dẫn về ``None`` chứ không ném lỗi: tệp này là bộ nhớ đệm,
    và một bộ nhớ đệm hỏng phải làm dịch vụ chậm đi chứ không được làm nó chết.
    """

    try:
        payload = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        if payload["version"] != CARD_CACHE_VERSION:
            return None
        if payload["fingerprint"] != fingerprint:
            return None
        return [
            Card(query_id, tuple(anchors), text, query)
            for query_id, anchors, text, query in payload["cards"]
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load_cards(
    store: ox.Store | None = None,
    *,
    ontology_path: Path = ONTOLOGY_PATH,
    catalogue_path: Path = QUERY_CATALOGUE_PATH,
    cache_path: Path = CARD_CACHE_PATH,
) -> list[Card]:
    """Bảng thẻ cho đường phục vụ: lấy tệp nướng sẵn nếu nó còn đúng.

    Dựng bảng thẻ là duyệt trọn ontology cho từng thực thể có tên, và kết quả chỉ
    phụ thuộc hai tệp - ontology và danh mục truy vấn. Việc ấy làm sẵn được lúc
    dựng ảnh, thay vì làm lại ở mỗi lần khởi động nguội.

    Vân tay là mã băm của chính hai tệp đó. Sửa ontology mà quên nướng lại thì
    tệp cũ bị bỏ qua và bảng thẻ được dựng như chưa từng có nó - chậm hơn, nhưng
    không bao giờ phục vụ bằng bảng thẻ của một ontology khác.
    """

    cached = _read_cache(cache_path, _fingerprint(ontology_path, catalogue_path))
    if cached is not None:
        return cached
    return build_cards(store, catalogue_path)


def bake_cards(
    destination: Path = CARD_CACHE_PATH,
    *,
    ontology_path: Path = ONTOLOGY_PATH,
    catalogue_path: Path = QUERY_CATALOGUE_PATH,
) -> list[Card]:
    """Dựng bảng thẻ một lần và ghi ra tệp, rồi đòi đọc lại phải giống hệt.

    Phép kiểm đọc-lại là thứ bước này chịu trách nhiệm: ghi ra rồi đọc vào không
    được làm rơi hay đổi gì. Nó rẻ, và kiểu hỏng nó chặn - một thẻ mất phần chữ
    hoặc lệch một neo - sẽ không lộ ra ở đâu khác cho tới lúc model chọn sai.
    """

    from .sparql import load_ontology

    cards = build_cards(load_ontology(ontology_path), catalogue_path)
    payload = {
        "version": CARD_CACHE_VERSION,
        "fingerprint": _fingerprint(ontology_path, catalogue_path),
        "cards": [
            [card.query_id, list(card.anchors), card.text, card.query]
            for card in cards
        ],
    }
    destination = Path(destination)
    destination.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    reloaded = _read_cache(destination, payload["fingerprint"])
    if reloaded != cards:
        raise SystemExit(
            f"bảng thẻ nướng sẵn không đọc lại đúng bản đã ghi: {destination}"
        )
    return cards
