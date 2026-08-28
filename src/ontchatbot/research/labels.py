"""Nhãn của bài phân loại, và tên tiếng Việt của từng nhóm câu hỏi.

Nhãn là cặp ``(query_id, danh sách IRI)`` giống hệt trường ``target`` của dataset,
nhưng khoản và điểm được gộp lên Điều chứa chúng. Gộp làm mất khả năng trả lời ở
cấp khoản/điểm, đổi lại đuôi dài co lại đủ để bộ phân loại làm việc được.

Tên hiển thị suy từ nhãn lớp trong ontology, không gõ tay, nên biểu đồ và báo cáo
luôn khớp với dữ liệu đang dùng.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pyoxigraph as ox

from ..settings import DATASET_DIR
from ..runtime.cards import (
    OWL_NAMED_INDIVIDUAL,
    RDF_TYPE,
    RDFS_LABEL,
    build_cards,
    objects,
    subjects_of_type,
    _literals,
    _shorten,
)
from ..runtime.sparql import load_ontology

ARTICLE = re.compile(r"^(:.*?Article\d+)")
SPLITS = ("train", "val", "test")


def merged_label(query_id: str, target) -> tuple[str, tuple[str, ...]]:
    """Nhãn của một dòng dataset, sau khi gộp khoản/điểm lên Điều."""
    if not target:
        return ("no-information", ())
    roots = sorted({(ARTICLE.match(a).group(1) if ARTICLE.match(a) else a) for a in target})
    return (query_id, tuple(roots))


def label_key(label) -> str:
    """Dạng chuỗi một dòng của nhãn, dùng khi lưu ra tệp."""
    return "|".join([label[0], *label[1]])


def load_splits(directory: Path = DATASET_DIR):
    """Ba tập dữ liệu, kèm chỉ số nhãn đã gộp gắn vào từng dòng."""
    rows = {}
    for split in SPLITS:
        with open(Path(directory) / f"{split}.jsonl", encoding="utf-8") as handle:
            rows[split] = [json.loads(line) for line in handle]
    labels = sorted({merged_label(r["query_id"], r["target"])
                     for part in rows.values() for r in part})
    index = {label: i for i, label in enumerate(labels)}
    for part in rows.values():
        for row in part:
            row["y"] = index[merged_label(row["query_id"], row["target"])]
    return rows, labels


def family_names(graph: ox.Store | None = None) -> dict[str, str]:
    """Tên tiếng Việt cho từng nhóm câu hỏi, suy từ nhãn lớp trong ontology."""
    graph = graph if graph is not None else load_ontology()

    classes, own = defaultdict(list), {}
    for subject in subjects_of_type(graph, OWL_NAMED_INDIVIDUAL):
        name = _shorten(subject)
        labels = _literals(graph, subject, RDFS_LABEL)
        if labels:
            own[name] = labels[0]
        # Xếp lớp theo IRI: một thực thể mang nhiều lớp thì thứ tự duyệt quyết
        # định cách phá hoà khi đếm phiếu bên dưới.
        for term in sorted(
            objects(graph, subject, RDF_TYPE), key=lambda node: node.value
        ):
            if term != OWL_NAMED_INDIVIDUAL:
                classes[name] += _literals(graph, term, RDFS_LABEL)

    votes, anchors = defaultdict(Counter), defaultdict(Counter)
    for card in build_cards(graph):
        if card.is_refusal:
            continue
        for iri in card.anchors:
            votes[card.query_id].update(classes.get(iri, []))
            if iri in own:
                anchors[card.query_id][own[iri]] += 1

    # Một nhóm có thể trộn nhiều lớp - "Điều / khoản / điểm" chẳng hạn. Lấy lớp
    # đông nhất khi nó áp đảo, còn không thì ghép vài lớp lớn nhất để tên không
    # hẹp hơn nội dung nhóm.
    names = {}
    for query_id, counts in votes.items():
        total = sum(counts.values())
        top, n = counts.most_common(1)[0]
        names[query_id] = (top if total and n / total >= 0.6
                           else " / ".join(k for k, _ in counts.most_common(3)))
    names["no-information"] = "Ngoài phạm vi (từ chối)"

    for round_ in range(2):
        clash = {n for n, c in Counter(names.values()).items() if c > 1}
        if not clash:
            break
        if round_ == 0:
            # Nhãn lớp trùng nhau thì lấy thẳng tên riêng của thực thể tiêu biểu:
            # nó ngắn hơn dạng ghép "lớp – chi tiết" và không bị cắt cụt thành
            # những nhãn nhìn giống hệt nhau trên biểu đồ.
            for query_id, name in list(names.items()):
                if name in clash and anchors[query_id]:
                    names[query_id] = anchors[query_id].most_common(1)[0][0]
        else:
            grouped = defaultdict(list)
            for query_id, name in names.items():
                if name in clash:
                    grouped[name].append(query_id)
            for name, ids in grouped.items():
                shared = set.intersection(*(set(i.split("-")) for i in ids))
                for query_id in ids:
                    tail = " ".join(t for t in query_id.split("-") if t not in shared)
                    names[query_id] = f"{name} [{tail}]" if tail else name
    return names
